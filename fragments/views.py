from __future__ import print_function

import logging
import numpy as np

from os import path
from django.http import JsonResponse
from rest_framework.decorators import api_view

from fragments.utils import (
    get_frag_by_loc, get_intra_chr_loops_from_looplist
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

    cooler_file = request.POST.get('cooler', False)
    loci = request.POST.get('loci', False)
    relative = request.GET.get('relative', False)

    try:
        precision = int(request.GET.get('precision', False))
    except ValueError:
        precision = False

    matrices = get_frag_by_loc(
        path.join('data', cooler_file),
        loci,
        is_rel=relative
    )

    if precision > 0:
        matrices = np.around(matrices, decimals=precision)

    fragments = []

    i = 0
    for matrix in matrices:
        fragments.append({
            'locus': loci[i],
            'matrix': matrix.tolist()
        })
        i += 1

    # Create results
    results = {
        'count': matrices.shape[0],
        'dim': matrices.shape[1],
        'fragments': fragments,
        'locusRel': relative
    }

    return JsonResponse(results)


@api_view(['GET'])
def fragments_by_chr(request):
    chrom = request.GET.get('chrom', False)
    cooler_file = request.GET.get('cooler', False)
    loop_list = request.GET.get('loop-list', False)

    try:
        zoomout_level = int(request.GET.get('zoomout_level', 0))
    except ValueError:
        zoomout_level = 0

    try:
        precision = int(request.GET.get('precision', False))
    except ValueError:
        precision = False

    # Get relative loci
    (loci_rel, chroms) = get_intra_chr_loops_from_looplist(
        path.join('data', loop_list), chrom
    )

    # Convert to chromosome-relative loci list
    loci_chrs_rel = np.column_stack(
        (chroms[:, 0], loci_rel[:, 0:2], chroms[:, 1], loci_rel[:, 2:4])
    )

    # Get fragments
    matrices = get_frag_by_loc(
        path.join('data', cooler_file),
        loci_chrs_rel,
        is_rel=True,
        zoomout_level=zoomout_level
    )

    if precision > 0:
        matrices = np.around(matrices, decimals=precision)

    fragments = []

    i = 0
    for matrix in matrices:
        fragments.append({
            'locus': loci_chrs_rel[i],
            'matrix': matrix.tolist()
        })
        i += 1

    # Create results
    results = {
        'count': matrices.shape[0],
        'dim': matrices.shape[1],
        'fragments': fragments,
        'locusRel': True,
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
        'loci': loci_rel_chroms.tolist()
    }

    return JsonResponse(results)
