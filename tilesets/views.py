from __future__ import print_function

import base64
import clodius.hdf_tiles as hdft
import clodius.db_tiles as cdt
import django.db.models as dbm
import cooler.contrib.higlass as cch
import guardian.utils as gu
import server.settings as hss
import h5py
import json
import logging
import math
import numpy as np
import os.path as op
import rest_framework.exceptions as rfe
import rest_framework.parsers as rfp
import rest_framework.status as rfs
import tilesets.models as tm
import tilesets.permissions as tsp
import tilesets.serializers as tss
import tilesets.suggestions as tsu
import slugid
import urllib
import redis
import pickle

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.gzip import gzip_page
from rest_framework import generics
from rest_framework import viewsets
from rest_framework.decorators import api_view
from tiles import make_tile

logger = logging.getLogger(__name__)

global mats
mats = {}


class EmptyRDB:
    def __init__(self):
        pass

    def exists(self, tile_id):
        return False

    def get(self, tile_id):
        return None

    def set(self, tile_id, tile_value):
        pass


global rdb

if hss.REDIS_HOST is not None:
    rdb = redis.Redis(
        host=hss.REDIS_HOST,
        port=hss.REDIS_PORT
    )
else:
    rdb = EmptyRDB()


def make_mats(dset):
    f = h5py.File(dset, 'r')
    mats[dset] = [f, cch.get_info(dset)]


def make_cooler_tile(cooler_filepath, tile_position):
    '''Create a tile from a cooler file.

    Args:
        cooler_filepath (str): The location of the cooler file that we'll
            that we'll extract the tile data from.
        tile_position (list): The position of the tile ([z,x,y])

    Returns:
        dict: The tile data consisting of a 'dense' member containing
            the data array as well as 'min_value' and 'max_value' which
            contain the minimum and maximum values in the 'dense' array.
    '''

    tile_data = {}

    if cooler_filepath not in mats:
        make_mats(cooler_filepath)

    tileset_file_and_info = mats[cooler_filepath]

    if tile_position[0] > tileset_file_and_info[1]['max_zoom']:
        # we don't have enough zoom levels
        return None
    if tile_position[1] >= 2 ** tile_position[0]:
        # tile is out of bounds
        return None
    if tile_position[2] >= 2 ** tile_position[0]:
        # tile is out of bounds
        return None

    tile = make_tile(
        tile_position[0],
        tile_position[1],
        tile_position[2],
        mats[cooler_filepath]
    )
    tile_data["min_value"] = float(np.min(tile))
    tile_data["max_value"] = float(np.max(tile))
    tile_data['dense'] = base64.b64encode(tile)

    return tile_data


def generate_tile(tile_id, request):
    '''
    Create a tile. The tile_id specifies the dataset as well
    as the position.

    This function will look at the filetype and determine what type
    of tile to retrieve (e..g cooler -> 2D dense, hitile -> 1D dense,
    elasticsearch -> anything)

    Args:
        tile_id (str): The id of a tile, consisting of the tileset id,
            followed by the tile position (e.g. PIYqJpdyTCmAZGmA6jNHJw.4.0.0)
        request (django.http.HTTPRequest): The request that included this tile.

    Returns:
        (string, dict): A tuple containing the tile ID tile data
    '''

    tile_id_parts = tile_id.split('.')
    tile_position = map(int, tile_id_parts[1:])
    tileset_uuid = tile_id_parts[0]

    tileset = tm.Tileset.objects.get(uuid=tileset_uuid)

    if tileset.private and request.user != tileset.owner:
        # dataset is not public return an empty set
        return (tileset_uuid, {'error': "Forbidden"})

    tile_value = rdb.get(tile_id)
    if tile_value is not None:
        tile_value = pickle.loads(tile_value)
        return (tile_id, tile_value)

    if tileset.filetype == "hitile":
        dense = hdft.get_data(
            h5py.File(
                get_datapath(tileset.datafile)
            ),
            tile_position[0],
            tile_position[1]
        )
        tile_value = {'dense': base64.b64encode(dense)}

    elif tileset.filetype == 'beddb':
        tile_value = cdt.get_tile(
            get_datapath(tileset.datafile),
            tile_position[0],
            tile_position[1]
        )

    elif tileset.filetype == 'bed2ddb':
        tile_value = cdt.get_2d_tile(
            get_datapath(tileset.datafile),
            tile_position[0],
            tile_position[1],
            tile_position[2]
        )

    elif tileset.filetype == 'hibed':
        dense = hdft.get_discrete_data(
            h5py.File(
                get_datapath(tileset.datafile)
            ),
            tile_position[0],
            tile_position[1]
        )

        tile_value = {'discrete': list([list(d) for d in dense])}

    elif tileset.filetype == "elasticsearch":
        response = urllib.urlopen(
            tileset.datafile + '/' + '.'.join(map(str, tile_position))
        )
        tile_value = json.loads(response.read())["_source"]["tile_value"]

    else:
        tile_value = make_cooler_tile(
            get_datapath(tileset.datafile), tile_position
        )
        if tile_value is None:
            return None

    rdb.set(tile_id, pickle.dumps(tile_value))
    return (tile_id, tile_value)


class UserList(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = tss.UserSerializer


class UserDetail(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = tss.UserSerializer


@api_view(['GET'])
def suggest(request):
    '''
    Suggest gene names based on the input text
    '''
    # suggestions are taken from a gene annotations tileset
    tileset_uuid = request.GET['d']
    text = request.GET['ac']

    try:
        tileset = tm.Tileset.objects.get(uuid=tileset_uuid)
    except:
        raise rfe.NotFound('Suggestion source file not found')

    result_dict = tsu.get_gene_suggestions(
        get_datapath(tileset.datafile), text
    )

    return JsonResponse(result_dict, safe=False)


@api_view(['GET', 'POST'])
def viewconfs(request):
    '''
    Retrieve a viewconfs with a given uid

    Args:

    request (django.http.HTTPRequest): The request object containing the
        uid (e.g. d=hg45ksdjfds) that identifies the viewconf.

    Return:

    '''
    if request.method == 'POST':
        uuid = slugid.nice()
        viewconf = request.body

        serializer = tss.ViewConfSerializer(data={'viewconf': request.body})
        if not serializer.is_valid():
            return JsonResponse(
                {'error': 'Serializer not valid'},
                status=rfs.HTTP_400_BAD_REQUEST
            )

        serializer.save(uuid=uuid, viewconf=viewconf)

        return JsonResponse({'uid': uuid})

    uuid = request.GET.get('d')

    obj = tm.ViewConf.objects.get(uuid=uuid)
    return JsonResponse(json.loads(obj.viewconf))


@api_view(['GET'])
def tiles(request):
    '''Retrieve a set of tiles

    A call to this API function should retrieve a few tiles.

    Args:
        request (django.http.HTTPRequest): The request object containing
            the parameters (e.g. d=x.0.0) that identify the tiles being
            requested.

    Returns:
        django.http.JsonResponse: A JSON object containing all of the tile
            data being requested. The JSON object is just a dictionary of
            (tile_id, tile_data) items.

    '''

    global mats

    # create a set so that we don't fetch the same tile multiple times
    tileids_to_fetch = set(request.GET.getlist("d"))
    # with ProcessPoolExecutor() as executor:
    # 	  res = executor.map(parallelize, hargs)
    '''
    p = mp.Pool(4)
    res = p.map(parallelize, hargs)
    '''

    res = map(lambda x: generate_tile(x, request), tileids_to_fetch)

    # create a dictionary of tileids
    result_dict = dict([i for i in res if i is not None])

    return JsonResponse(result_dict, safe=False)


def get_datapath(relpath):
    return op.join(hss.BASE_DIR, relpath)


@api_view(['GET'])
def tileset_info(request):
    ''' Get information about a tileset

    Tilesets have information critical to their display
    such as the maximum number of dimensions and well as
    their width. This needs to be relayed to the client
    in order for it to know which tiles to request.

    Args:
        request (django.http.HTTPRequest): The request object
            containing tileset_ids in the 'd' parameter.
    Return:
        django.http.JsonResponse: A JSON object containing
            the tileset meta-information
    '''
    global mats
    queryset = tm.Tileset.objects.all()
    tileset_uuids = request.GET.getlist("d")
    tileset_infos = {}
    for tileset_uuid in tileset_uuids:
        tileset_object = queryset.filter(uuid=tileset_uuid).first()

        if tileset_object is None:
            return JsonResponse({
                'error': 'No such tileset with uuid: {}'.format(tileset_uuid)
            }, status=500)

        if tileset_object.private and request.user != tileset_object.owner:
            return JsonResponse({
                'error': 'Data set (uuid: {}) is not public'.format(
                    tileset_uuid
                )
            }, status=403)

        if (
            tileset_object.filetype == "hitile" or
            tileset_object.filetype == 'hibed'
        ):
            tileset_info = hdft.get_tileset_info(
                h5py.File(get_datapath(tileset_object.datafile)))
            tileset_infos[tileset_uuid] = {
                "min_pos": [0],
                "max_pos": [tileset_info['max_pos']],
                "max_width": 2 ** math.ceil(
                    math.log(tileset_info['max_pos'] - 0) / math.log(2)
                ),
                "tile_size": tileset_info['tile_size'],
                "max_zoom": tileset_info['max_zoom']
            }
        elif tileset_object.filetype == "elastic_search":
            response = urllib.urlopen(
                tileset_object.datafile + "/tileset_info")
            tileset_infos[tileset_uuid] = json.loads(response.read())
        elif tileset_object.filetype == 'beddb':
            tileset_infos[tileset_uuid] = cdt.get_tileset_info(
                get_datapath(tileset_object.datafile)
            )
        elif tileset_object.filetype == 'bed2ddb':
            tileset_infos[tileset_uuid] = cdt.get_2d_tileset_info(
                get_datapath(tileset_object.datafile)
            )
        else:
            dsetname = get_datapath(tileset_object.datafile)

            if dsetname not in mats:
                try:
                    make_mats(dsetname)
                except Exception:
                    return JsonResponse({
                        'error': 'File not found (uuid: {})'.format(
                            tileset_uuid
                        )
                    }, status=500)

            tileset_infos[tileset_uuid] = mats[dsetname][1]

        tileset_infos[tileset_uuid]['name'] = tileset_object.name

    return JsonResponse(tileset_infos)


@method_decorator(gzip_page, name='dispatch')
class TilesetsViewSet(viewsets.ModelViewSet):
    """Tilesets"""

    queryset = tm.Tileset.objects.all()
    serializer_class = tss.TilesetSerializer
    permission_classes = (tsp.UserPermission,)
    lookup_field = 'uuid'
    parser_classes = (rfp.MultiPartParser,)

    def list(self, request, *args, **kwargs):
        '''List the available tilesets

        Args:
            request (django.http.HTTPRequest): The HTTP request containing
                no parameters

        Returns:
            django.http.JsonResponse: A json file containing a 'count' as
                well as 'results' with each tileset as an entry
        '''
        # only return tilesets which are accessible by this user
        if request.user.is_anonymous:
            user = gu.get_anonymous_user()
        else:
            user = request.user

        queryset = self.queryset.filter(
            dbm.Q(owner=user) | dbm.Q(private=False)
        )

        if 'ac' in request.GET:
            # Autocomplete fields
            queryset = queryset.filter(name__contains=request.GET['ac'])
        if 't' in request.GET:
            # Filter by filetype
            queryset = queryset.filter(filetype=request.GET['t'])
        if 'dt' in request.GET:
            # Filter by datatype
            queryset = queryset.filter(datatype__in=request.GET.getlist('dt'))

        ts_serializer = tss.UserFacingTilesetSerializer(queryset, many=True)
        return JsonResponse(
            {"count": len(queryset), "results": ts_serializer.data}
        )

    def perform_create(self, serializer):
        '''Add a new tileset

        When adding a new dataset, we need to enforce permissions as well as
        other rules like the uniqueness of uuids.

        Args:
            serializer (tilsets.serializer.TilesetSerializer): The serializer
            to use to save the request.
        '''
        if 'uid' in self.request.data:
            try:
                self.queryset.get(uuid=self.request.data['uid'])
                # this uid already exists, return an error
                raise rfe.APIException("UID already exists")
            except tm.Tileset.DoesNotExist:
                uid = self.request.data['uid']
        else:
            uid = slugid.nice()

        if 'filetype' not in self.request.data:
            raise rfe.APIException('Missing filetype')

        datatype = None
        if 'datatype' not in self.request.data:
            if self.request.data['filetype'] == 'cooler':
                datatype = 'matrix'
            elif self.request.data['filetype'] == 'hitile':
                datatype = 'vector'
            else:
                raise rfe.APIException(
                    'Missing datatype. Could not infer from filetype:',
                    self.request.data['filetype']
                )

        datafile = self.request.data.get('datafile')

        if 'name' in self.request.data:
            name = self.request.data['name']
        else:
            name = op.split(datafile.name)[1]

        serializer.save(owner=self.request.user, name=name, uuid=uid)

        # if self.request.user.is_anonymous:
        #     # can't create a private dataset as an anonymous user
        #     serializer.save(
        #         owner=gu.get_anonymous_user(),
        #         private=False,
        #         name=name,
        #         uuid=uid
        #     )
        # else:
        #     serializer.save(owner=self.request.user, name=name, uuid=uid)
