**WARNING | OUTDATED**:

This repo is not actively maintained any more. Please use [HiGlass Server](https://github.com/hms-dbmi/higlass-server) instead. The code and functionality as be merged and is continuously expanded.

---

# HiPiler Server

> This is a clean clone of [HiGlass Server](https://github.com/hms-dbmi/higlass-server) extended with extra endpoints for [HiPiler](https://github.com/flekschas/hipiler)

## Installation

```bash
git clone https://github.com/hms-dbmi/higlass-server mdm-server && cd mdm-server
mkvirtualenv -a $(pwd) mdm-server
pip install cython
pip install --upgrade -r requirements.txt
./manage.py migrate
./manage.py runserver localhost:8000
```

---

## Content

### Add Data

These steps are optional in case one wants to start with a pre-populated database.

```
COOL=dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool
HITILE=wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile

wget https://s3.amazonaws.com/pkerp/public/$COOL
mv $COOL data/

wget https://s3.amazonaws.com/pkerp/public/$HITILE
mv $HITILE data/

curl -F "datafile=@data/$COOL" -F "filetype=cooler" -F "datatype=matrix" -F "uid=aa" http://localhost:8000/tilesets/
curl -F "datafile=@data/$HITILE" -F "filetype=hitile" -F "datatype=vector" -F "uid=bb" http://localhost:8000/tilesets/
```

The "uid" parameter is optional, and if it were missing, one would be generated.
This uuid can be used to retrieve tiles:

Get tileset info:

```
curl http://localhost:8000/tileset_info/?d=aa
```

Get a tile:

```
curl http://localhost:8000/tiles/?d=aa.0.0.0
```

### Preparing Cooler Files

[Cooler](https://github.com/mirnylab/cooler) files store Hi-C data. They need to be decorated with aggregated data at multiple resolutions in order to work with `higlass-server`.
This is easily accomplished by simply installing the `cooler` python package and running the `recursive_agg_onefile.py` script. For now this has to come from a clone of the
official cooler repository, but this will hopefully be merged into the main branch shortly.

```

git clone -b develop https://github.com/pkerpedjiev/cooler.git
cd cooler
python setup.py install

recursive_agg_onefile.py file.cooler --out output.cooler
```

### Preparing bigWig files for use with `higlass-server`

[BigWig](https://genome.ucsc.edu/goldenpath/help/bigWig.html) files contain values for positions along a genome. To be viewable using higlass, they need to be aggregated using `clodius`:

Installing `clodius`:

```
pip install clodius
```

Getting a sample dataset:

```
wget http://hgdownload.cse.ucsc.edu/goldenpath/hg19/encodeDCC/wgEncodeCaltechRnaSeq/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.bigWig
```

Aggregate it:

```
tile_bigWig.py wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.bigWig --output-file data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile
```

Register it:

```
curl -H "Content-Type: application/json" -X POST -d '{"processed_file":"data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2","file_type":"hitile"}' http://localhost:8000/tilesets/
```

### Unit tests

```
wget -O -P data/ https://s3.amazonaws.com/pkerp/public/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool
wget -O -P data/ https://s3.amazonaws.com/pkerp/public/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile
wget -O -P data/ https://s3.amazonaws.com/pkerp/public/gene_annotations.short.db

python manage.py test tilesets
```

### Upgrade

```
bumpversion patch
```

---

## Examples

### Queries

**GET**: `/api/v1/fragments_by_chr/?precision=2&cooler=Rao2014-GM12878-MboI-allreps-filtered.1kb.multires.cool&zoomout-level=2&chrom=22&loop-list=GSE63525_GM12878_primary%2breplicate_HiCCUPS_looplist.txt`

_Note_: `cooler` can also be the uuid specified for higlass, e.g., `rao1kbmr`

Response:
```
{
  "count": 163,
  "dims": 22,
  "fragments": [
    {
      "end1": 17400000,
      "end2": 17540000,
      "matrix": [
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0.3,0,0,0,0,0,0.33,0.49,0.4,0.6,0.63,0.79,0.57,0.4,0.5,0.26,0.27,0.18,0.11,0.17,0.22,0.25],
        [0.44,0,0,0,0,0,0.6,0.42,0.56,0.6,0.84,1,0.69,0.69,0.4,0.31,0.31,0.31,0.3,0.17,0.13,0.13],
        [0.34,0,0,0,0,0,0.18,0.46,0.56,0.67,0.62,0.84,0.64,0.8,0.3,0.41,0.31,0.43,0.3,0.15,0.15,0.24],
        [0.47,0,0,0,0,0,0.69,0.49,0.45,0.66,0.71,0.69,0.77,0.5,0.44,0.37,0.21,0.14,0.22,0.19,0.23,0.14],
        [0.49,0,0,0,0,0,0.39,0.48,0.42,0.52,0.45,0.67,0.59,0.47,0.42,0.29,0.24,0.3,0.16,0.14,0.17,0.11],
        [0.47,0,0,0,0,0,0.32,0.32,0.51,0.41,0.55,0.6,0.52,0.46,0.44,0.29,0.3,0.18,0.27,0.28,0.16,0.14],
        [0.24,0,0,0,0,0,0.68,0.18,0.36,0.52,0.41,0.59,0.35,0.32,0.42,0.33,0.19,0.19,0.21,0.25,0.1,0.29],
        [0.67,0,0,0,0,0,0.56,0.4,0.57,0.33,0.44,0.66,0.2,0.31,0.38,0.29,0.23,0.16,0.38,0.21,0.28,0.25],
        [0.59,0,0,0,0,0,0.2,0.39,0.43,0.49,0.43,0.66,0.42,0.34,0.31,0.25,0.29,0.16,0.2,0.14,0.11,0.27],
        [0.44,0,0,0,0,0,0.31,0.45,0.45,0.47,0.45,0.38,0.57,0.29,0.32,0.18,0.29,0.28,0.25,0.26,0.17,0.12],
        [0.43,0,0,0,0,0,0.45,0.21,0.37,0.57,0.25,0.53,0.34,0.43,0.25,0.32,0.17,0.22,0.28,0.21,0.18,0.15],
        [0.58,0,0,0,0,0,0.54,0.36,0.36,0.36,0.4,0.4,0.26,0.28,0.28,0.23,0.26,0.23,0.29,0.2,0.12,0.16]
      ],
      "start2": 17535000,
      "start1": 17395000,
      "chrom1": "22",
      "chrom2": "22"
    },
    ...
  ],
  "relativeLoci": true,
  "zoomoutLevel": 2
}
```

**POST**: `/api/v1/fragments_by_loci/`

_Note_: `cooler` can also be the uuid specified for higlass, e.g., `rao1kbmr`

Data:
```
{
  "cooler": "Rao2014-GM12878-MboI-allreps-filtered.1kb.multires.cool",
  "precision": 2,
  "zoomoutLevel": 2,
  "loci": [
    {
      "end1": 17400000,
      "end2": 17540000,
      "start2": 17535000,
      "start1": 17395000,
      "chrom1": "22",
      "chrom2": "22"
    }
  ]
}
```

Response:
```
{
  "count": 1,
  "dim": 22,
  "fragments": [
    {
      "end1": 17400000,
      "end2": 17540000,
      "matrix": [
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0.3,0,0,0,0,0,0.33,0.49,0.4,0.6,0.63,0.79,0.57,0.4,0.5,0.26,0.27,0.18,0.11,0.17,0.22,0.25],
        [0.44,0,0,0,0,0,0.6,0.42,0.56,0.6,0.84,1,0.69,0.69,0.4,0.31,0.31,0.31,0.3,0.17,0.13,0.13],
        [0.34,0,0,0,0,0,0.18,0.46,0.56,0.67,0.62,0.84,0.64,0.8,0.3,0.41,0.31,0.43,0.3,0.15,0.15,0.24],
        [0.47,0,0,0,0,0,0.69,0.49,0.45,0.66,0.71,0.69,0.77,0.5,0.44,0.37,0.21,0.14,0.22,0.19,0.23,0.14],
        [0.49,0,0,0,0,0,0.39,0.48,0.42,0.52,0.45,0.67,0.59,0.47,0.42,0.29,0.24,0.3,0.16,0.14,0.17,0.11],
        [0.47,0,0,0,0,0,0.32,0.32,0.51,0.41,0.55,0.6,0.52,0.46,0.44,0.29,0.3,0.18,0.27,0.28,0.16,0.14],
        [0.24,0,0,0,0,0,0.68,0.18,0.36,0.52,0.41,0.59,0.35,0.32,0.42,0.33,0.19,0.19,0.21,0.25,0.1,0.29],
        [0.67,0,0,0,0,0,0.56,0.4,0.57,0.33,0.44,0.66,0.2,0.31,0.38,0.29,0.23,0.16,0.38,0.21,0.28,0.25],
        [0.59,0,0,0,0,0,0.2,0.39,0.43,0.49,0.43,0.66,0.42,0.34,0.31,0.25,0.29,0.16,0.2,0.14,0.11,0.27],
        [0.44,0,0,0,0,0,0.31,0.45,0.45,0.47,0.45,0.38,0.57,0.29,0.32,0.18,0.29,0.28,0.25,0.26,0.17,0.12],
        [0.43,0,0,0,0,0,0.45,0.21,0.37,0.57,0.25,0.53,0.34,0.43,0.25,0.32,0.17,0.22,0.28,0.21,0.18,0.15],
        [0.58,0,0,0,0,0,0.54,0.36,0.36,0.36,0.4,0.4,0.26,0.28,0.28,0.23,0.26,0.23,0.29,0.2,0.12,0.16]
      ],
      "start2": 17535000,
      "start1": 17395000,
      "chrom1": "22",
      "chrom2": "22"
    }
  ],
  "relativeLoci": true,
  "zoomoutLevel": 2
}
```

**GET**: `/api/v1/loci?chrom=22&loop-list=GSE63525_GM12878_primary%2breplicate_HiCCUPS_looplist.txt`

Response:
```
{
  "loci": [
    {
      "end1": 17400000,
      "end2": 17540000,
      "start2": 17535000,
      "start1": 17395000,
      "chrom1": "22",
      "chrom2": "22"
    },
    ...
```
