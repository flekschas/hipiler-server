from __future__ import print_function

import logging
import numpy as np

from os import path
from django.http import JsonResponse
from rest_framework.decorators import api_view
import server.settings as settings

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

    loci = request.POST.get('loci', False)
    cooler_file = request.POST.get('cooler', False)

    fragments = get_frag_by_loc(path.join('data', cooler_file), loci)

    # Create results
    results = {
        'fragments': fragments.tolist()
    }

    return JsonResponse(results)


@api_view(['GET'])
def fragments_by_chr(request):
    chrom = request.GET.get('chrom', False)
    cooler_file = request.GET.get('cooler', False)
    loop_list = request.GET.get('loop-list', False)

    try:
        precision = int(request.GET.get('precision', False))
    except ValueError:
        precision = False

    logger.debug(cooler_file, chrom, loop_list)

    print(settings.BASE_DIR)

    # Get relative loci
    (loci_rel, chroms) = get_intra_chr_loops_from_looplist(
        path.join('data', loop_list), chrom
    )

    # Convert to chromosome-relative loci list
    loci_chrs_rel = np.column_stack(
        (chroms[:, 0], loci_rel[:, 0:2], chroms[:, 1], loci_rel[:, 2:4])
    )

    # Get fragments
    fragments = get_frag_by_loc(
        path.join('data', cooler_file),
        loci_chrs_rel,
        is_rel=True
    )

    if precision > 0:
        fragments = np.around(fragments, decimals=precision)

    # Create results
    results = {
        'fragments': fragments.tolist()
    }

    return JsonResponse(results)
