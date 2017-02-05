from __future__ import print_function

import logging
import numpy as np

from os import path
from django.http import JsonResponse
from rest_framework.decorators import api_view

from fragments.utils import (
    get_frag_by_loc,
    get_intra_chr_loops_from_looplist,
    rel_loci_2_obj
)

logger = logging.getLogger(__name__)


@api_view(['POST'])
def fragments_by_loci(request):
    '''
    Retrieve a list of locations and return the corresponding matrix fragments

    Args:

    request (django.http.HTTPRequest): The request object containing the
        list of loci.

    Return:

    '''

    try:
        cooler_file = request.data['cooler']
    except ValueError:
        cooler_file = False

    try:
        loci = request.data['loci']
    except ValueError:
        loci = []

    try:
        zoomout_level = int(request.data.get('zoomoutLevel', -1))
    except ValueError:
        zoomout_level = -1

    try:
        precision = int(request.data.get('precision', False))
    except ValueError:
        precision = False

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

    print(loci_list)

    try:
        matrices = get_frag_by_loc(
            path.join('data', cooler_file),
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

    return JsonResponse(results)


@api_view(['GET'])
def fragments_by_chr(request):
    chrom = request.GET.get('chrom', False)
    cooler_file = request.GET.get('cooler', False)
    loop_list = request.GET.get('loop-list', False)

    try:
        zoomout_level = int(request.GET.get('zoomout-level', -1))
    except ValueError:
        zoomout_level = -1

    try:
        precision = int(request.GET.get('precision', False))
    except ValueError:
        precision = False

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

    # Get fragments
    try:
        matrices = get_frag_by_loc(
            path.join('data', cooler_file),
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

    i = 0
    for matrix in matrices:
        frag_obj = {
            'matrix': matrix.tolist()
        }
        frag_obj.update(loci_struct[i])
        fragments.append(frag_obj)
        i += 1

    # Create results
    results = {
        'count': matrices.shape[0],
        'dims': matrices.shape[1],
        'fragments': fragments,
        'relativeLoci': True,
        'zoomoutLevel': zoomout_level
    }

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
