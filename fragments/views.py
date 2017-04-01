from __future__ import print_function

from django.core.cache import cache

from rest_framework.authentication import BasicAuthentication
from drf_disable_csrf import CsrfExemptSessionAuthentication

import hashlib
import json
import logging
import numpy as np

from os import path
from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import api_view, authentication_classes

from tilesets.models import Tileset
from fragments.models import ChromInfo, ChromSizes

from operator import itemgetter

from fragments.utils import (
    calc_measure_dtd,
    calc_measure_size,
    calc_measure_noise,
    calc_measure_sharpness,
    get_frag_by_loc,
    get_intra_chr_loops_from_looplist,
    rel_loci_2_obj
)

logger = logging.getLogger(__name__)

SUPPORTED_MEASURES = ['distance-to-diagonal', 'noise', 'size', 'sharpness']


@api_view(['POST'])
@authentication_classes((CsrfExemptSessionAuthentication, BasicAuthentication))
def fragments_by_loci(request):
    '''
    Retrieve a list of locations and return the corresponding matrix fragments

    Args:

    request (django.http.HTTPRequest): The request object containing the
        list of loci.

    Return:

    '''

    loci = request.data.get('loci', [])

    try:
        precision = int(request.GET.get('precision', False))
    except ValueError:
        precision = False

    try:
        no_cache = bool(request.GET.get('no-cache', False))
    except ValueError:
        no_cache = False

    try:
        dims = int(request.GET.get('dims', 22))
    except ValueError:
        dims = 22

    try:
        no_balance = bool(request.GET.get('no-balance', False))
    except ValueError:
        no_balance = False

    '''
    Loci list must be of type:
    0: chrom1
    1: start1
    2: end1
    3: chrom2
    4: start2
    5: end2
    6: dataset
    7: zoomOutLevel [0]
    '''

    i = 0
    loci_lists = {}
    try:
        for locus in loci:
            cooler_file = ''

            if locus[6]:
                if locus[6].endswith('.cool'):
                    cooler_file = path.join('data', locus[6])
                else:
                    try:
                        cooler_file = Tileset.objects.get(
                            uuid=locus[6]
                        ).datafile
                    except AttributeError:
                        return JsonResponse({
                            'error': 'Dataset (cooler file) not in database',
                        }, status=500)
            else:
                return JsonResponse({
                    'error': 'Dataset (cooler file) not specified',
                }, status=500)

            if cooler_file not in loci_lists:
                loci_lists[cooler_file] = {}

            if locus[7] not in loci_lists[cooler_file]:
                loci_lists[cooler_file][locus[7]] = []

            loci_lists[cooler_file][locus[7]].append(locus[0:6] + [i])

            i += 1

    except Exception as e:
        return JsonResponse({
            'error': 'Could not convert loci.',
            'error_message': str(e)
        }, status=500)

    # Get a unique string for caching
    uuid = hashlib.md5(
        json.dumps(loci, sort_keys=True) + str(precision) + str(dims)
    ).hexdigest()

    # Check if something is cached
    if not no_cache:
        results = cache.get('frag_by_loci_%s' % uuid, False)

        if results:
            return JsonResponse(results)

    matrices = []
    try:
        for dataset in loci_lists:
            for zoomout_level in loci_lists[dataset]:
                raw_matrices = get_frag_by_loc(
                    dataset,
                    loci_lists[dataset][zoomout_level],
                    zoomout_level=zoomout_level,
                    dim=dims,
                    balanced=not no_balance
                )

                if precision > 0:
                    raw_matrices = np.around(raw_matrices, decimals=precision)

                i = 0
                for raw_matrix in raw_matrices:
                    matrices.append({
                        'id': loci_lists[dataset][zoomout_level][i][6],
                        'raw': raw_matrix
                    })
                    i += 1
    except Exception as e:
        return JsonResponse({
            'error': 'Could not retrieve fragments.',
            'error_message': str(e)
        }, status=500)

    # Sort matrices
    matrices_sorted = sorted(matrices, key=itemgetter('id'))

    fragments = []

    i = 0
    for matrix in matrices_sorted:
        fragments.append(matrix['raw'].tolist())
        i += 1

    # Create results
    results = {
        'fragments': fragments
    }

    # Cache results for 8 hour
    cache.set('frag_by_loci_%s' % uuid, results, 60 * 60 * 8)

    return JsonResponse(results)


@api_view(['GET'])
@authentication_classes((CsrfExemptSessionAuthentication, BasicAuthentication))
def fragments_by_chr(request):
    chrom = request.GET.get('chrom', False)
    cooler_file = request.GET.get('cooler', False)
    loop_list = request.GET.get('loop-list', False)

    if cooler_file:
        if cooler_file.endswith('.cool'):
            cooler_file = path.join('data', cooler_file)
        else:
            try:
                cooler_file = Tileset.objects.get(uuid=cooler_file).datafile
            except AttributeError:
                return JsonResponse({
                    'error': 'Cooler file not in database',
                }, status=500)
    else:
        return JsonResponse({
            'error': 'Cooler file not specified',
        }, status=500)

    try:
        measures = request.GET.getlist('measures', [])
    except ValueError:
        measures = []

    try:
        zoomout_level = int(request.GET.get('zoomout-level', -1))
    except ValueError:
        zoomout_level = -1

    try:
        limit = int(request.GET.get('limit', -1))
    except ValueError:
        limit = -1

    try:
        precision = int(request.GET.get('precision', False))
    except ValueError:
        precision = False

    try:
        no_cache = bool(request.GET.get('no-cache', False))
    except ValueError:
        no_cache = False

    try:
        for_config = bool(request.GET.get('for-config', False))
    except ValueError:
        for_config = False

    # Get a unique string for the URL query string
    uuid = hashlib.md5(
        '-'.join([
            cooler_file,
            chrom,
            loop_list,
            str(limit),
            str(precision),
            str(zoomout_level)
        ])
    ).hexdigest()

    # Check if something is cached
    if not no_cache:
        results = cache.get('frag_by_chrom_%s' % uuid, False)

        if results:
            return JsonResponse(results)

    # Get relative loci
    try:
        (loci_rel, chroms) = get_intra_chr_loops_from_looplist(
            path.join('data', loop_list), chrom
        )
    except Exception as e:
        return JsonResponse({
            'error': 'Could not retrieve loci.',
            'error_message': str(e)
        }, status=500)

    # Convert to chromosome-relative loci list
    loci_rel_chroms = np.column_stack(
        (chroms[:, 0], loci_rel[:, 0:2], chroms[:, 1], loci_rel[:, 2:4])
    )

    if limit > 0:
        loci_rel_chroms = loci_rel_chroms[:limit]

    # Get fragments
    try:
        matrices = get_frag_by_loc(
            cooler_file,
            loci_rel_chroms,
            zoomout_level=zoomout_level
        )
    except Exception as e:
        return JsonResponse({
            'error': 'Could not retrieve fragments.',
            'error_message': str(e)
        }, status=500)

    if precision > 0:
        matrices = np.around(matrices, decimals=precision)

    fragments = []

    loci_struct = rel_loci_2_obj(loci_rel_chroms)

    # Check supported measures
    measures_applied = []
    for measure in measures:
        if measure in SUPPORTED_MEASURES:
            measures_applied.append(measure)

    i = 0
    for matrix in matrices:
        measures_values = []

        for measure in measures:
            if measure == 'distance-to-diagonal':
                measures_values.append(
                    calc_measure_dtd(matrix, loci_struct[i])
                )

            if measure == 'size':
                measures_values.append(
                    calc_measure_size(matrix, loci_struct[i])
                )

            if measure == 'noise':
                measures_values.append(calc_measure_noise(matrix))

            if measure == 'sharpness':
                measures_values.append(calc_measure_sharpness(matrix))

        frag_obj = {
            # 'matrix': matrix.tolist()
        }

        frag_obj.update(loci_struct[i])
        frag_obj.update({
            "measures": measures_values
        })
        fragments.append(frag_obj)
        i += 1

    # Create results
    results = {
        'count': matrices.shape[0],
        'dims': matrices.shape[1],
        'fragments': fragments,
        'measures': measures_applied,
        'relativeLoci': True,
        'zoomoutLevel': zoomout_level
    }

    if for_config:
        results['fragmentsHeader'] = [
            'chrom1',
            'start1',
            'end1',
            'strand1',
            'chrom2',
            'start2',
            'end2',
            'strand2'
        ] + measures_applied

        fragments_arr = []
        for fragment in fragments:
            tmp = [
                fragment['chrom1'],
                fragment['start1'],
                fragment['end1'],
                fragment['strand1'],
                fragment['chrom2'],
                fragment['start2'],
                fragment['end2'],
                fragment['strand2'],
            ] + fragment['measures']

            fragments_arr.append(tmp)

        results['fragments'] = fragments_arr

    # Cache results for an hour
    cache.set('frag_by_chrom_%s' % uuid, results, 60 * 60)

    return JsonResponse(results)


@api_view(['GET'])
@authentication_classes((CsrfExemptSessionAuthentication, BasicAuthentication))
def loci(request):
    chrom = request.GET.get('chrom', False)
    loop_list = request.GET.get('loop-list', False)

    # Get relative loci
    (loci_rel, chroms) = get_intra_chr_loops_from_looplist(
        path.join('data', loop_list), chrom
    )

    loci_rel_chroms = np.column_stack(
        (chroms[:, 0], loci_rel[:, 0:2], chroms[:, 1], loci_rel[:, 2:4])
    )

    # Create results
    results = {
        'loci': rel_loci_2_obj(loci_rel_chroms)
    }

    return JsonResponse(results)


@api_view(['GET'])
@authentication_classes((CsrfExemptSessionAuthentication, BasicAuthentication))
def chromInfo(request):
    coords = request.GET.get('coords', False)

    try:
        chrom_info = ChromInfo.objects.get(uuid=coords)
    except Exception as e:
        return JsonResponse({})

    try:
        with open(chrom_info.datafile) as f:
            data = json.load(f)
    except Exception as e:
        return JsonResponse({})

    return JsonResponse(data)


@api_view(['GET'])
@authentication_classes((CsrfExemptSessionAuthentication, BasicAuthentication))
def chromSizes(request):
    coords = request.GET.get('coords', False)

    try:
        chrom_sizes = ChromSizes.objects.get(uuid=coords)
    except Exception as e:
        return HttpResponse({
            error: 'ChromSizes for %s not found' % coords
        })

    try:
        with open(chrom_sizes.datafile) as f:
            data = f.readlines()
    except Exception as e:
        return HttpResponse({
            error: 'Could not load file %s' % chrom_sizes.datafile
        })

    return HttpResponse(data)
