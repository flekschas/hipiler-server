from __future__ import print_function

from django.core.cache import cache

import hashlib
import logging
import numpy as np
from django.views.decorators.csrf import csrf_exempt

from os import path
from django.http import JsonResponse
from rest_framework.decorators import api_view

from tilesets.models import Tileset

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


@csrf_exempt
@api_view(['POST'])
def fragments_by_loci(request):
    '''
    Retrieve a list of locations and return the corresponding matrix fragments

    Args:

    request (django.http.HTTPRequest): The request object containing the
        list of loci.

    Return:

    '''

    cooler_file = request.data.get('cooler', False)

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

    loci = request.data.get('loci', [])

    try:
        zoomout_level = int(request.data.get('zoomoutLevel', -1))
    except ValueError:
        zoomout_level = -1

    try:
        limit = int(request.data.get('limit', -1))
    except ValueError:
        limit = -1

    try:
        precision = int(request.data.get('precision', False))
    except ValueError:
        precision = False

    try:
        no_cache = bool(request.GET.get('no-cache', False))
    except ValueError:
        no_cache = False

    try:
        loci_list = []
        for locus in loci:
            loci_list.append([
                locus['chrom1'],
                locus['start1'],
                locus['end1'],
                locus['chrom2'],
                locus['start2'],
                locus['end2']
            ])
    except Exception as e:
        return JsonResponse({
            'error': 'Could not convert loci.',
            'error_message': str(e)
        }, status=500)

    # Get a unique string for the URL query string
    uuid = hashlib.md5(
        '-'.join([
            cooler_file,
            loci,
            str(limit),
            str(precision),
            str(zoomout_level)
        ])
    ).hexdigest()

    # Check if something is cached
    if not no_cache:
        results = cache.get('frag_by_loci_%s' % uuid, False)

        if results:
            return JsonResponse(results)

    if limit > 0:
        loci_list = loci_list[:limit]

    try:
        matrices = get_frag_by_loc(
            cooler_file,
            loci_list,
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

    i = 0
    for matrix in matrices:
        frag_obj = {
            'matrix': matrix.tolist()
        }
        frag_obj.update(loci[i])
        fragments.append(frag_obj)
        i += 1

    # Create results
    results = {
        'count': matrices.shape[0],
        'dim': matrices.shape[1],
        'fragments': fragments,
        'relativeLoci': True,
        'zoomoutLevel': zoomout_level
    }

    # Cache results for an hour
    cache.set('frag_by_loci_%s' % uuid, results, 60 * 60)

    return JsonResponse(results)


@api_view(['GET'])
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
            'matrix': matrix.tolist()
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

    # Cache results
    cache.set('frag_by_chrom_%s' % uuid, results, 60 * 15)

    return JsonResponse(results)


@api_view(['GET'])
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
