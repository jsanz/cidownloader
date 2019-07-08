import atoma, requests, os, subprocess
from urllib import request, parse
import zipfile
import shutil
import click


atom_buildings = 'http://www.catastro.minhap.es/INSPIRE/buildings/ES.SDGC.BU.atom.xml'
atom_parcels = 'http://www.catastro.minhap.es/INSPIRE/CadastralParcels/ES.SDGC.CP.atom.xml'
atom_addresses = 'http://www.catastro.minhap.es/INSPIRE/Addresses/ES.SDGC.AD.atom.xml'

def format_codmun(provincia, municipio):
    return str(provincia).zfill(2) + str(municipio).zfill(3)


def parseurl(url):

    url = parse.urlsplit(url)
    url = list(url)
    url[2] = parse.quote(url[2])
    parsed_url = parse.urlunsplit(url)
    return parsed_url


def download_municipio(url, epsg, output_gpkg, to_epsg=None):
    """
    Descarga un gml de catastro a partir de una url y un epgs.
    Lo convierte a geopackage.
    Permite declarar un epsg de destino.
    """
    if not to_epsg:
        to_epsg = epsg

    try:
        try:
            os.makedirs('downloads')
        except:
            pass
        filename, headers = request.urlretrieve(url)
        with zipfile.ZipFile(os.path.join(filename) , "r") as z:
            z.extractall(path=os.path.join(os.curdir, 'downloads'))
        for gml in os.listdir('downloads'):
            if os.path.splitext(gml)[1] == '.gml':
                layername = gml.split('.')[5]
                ogr_cmd = """ogr2ogr -update -append -f GPKG -s_srs EPSG:{} -t_srs EPSG:{} -lco IDENTIFIER={} {} {}""".format(epsg, to_epsg, layername, output_gpkg + '.gpkg', os.path.join('downloads', gml))
                # print ("\n Executing: ", ogr_cmd)
                subprocess.run(ogr_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print("Error: {}".format(str(e)))
    finally:
        shutil.rmtree('downloads')


def read_prov_atom(atom_url, codmun=None):
    """
    Lee el atom específico para cada parroquia. 
    
    Devuelve el url del Atom de cada municipio con su epsg.

    Se puede pasar un parámetro codmun para devolver sólo este municipio.
    """

    response = requests.get(atom_url)

    feed = atoma.parse_atom_bytes(response.content)

    urls = []
    for entry in feed.entries:
        url = parseurl(entry.links[0].href)
        epsg = entry.categories[0].term.split('/')[-1]
        codmun_atom = os.path.basename(url).split('.')[4]

        if codmun is None or codmun == codmun_atom:
            urls.append((url, epsg))

    return urls


def read_complete_atom(provincia=None):
    """
    Lee el atom general de Catastro Inspire que contiene los diferentes
    Atoms para cada provincia.

    Devuelve una lista con url a los atoms y el título.
    """

    url = atom_buildings
    response = requests.get(url)
    feed = atoma.parse_atom_bytes(response.content)

    atoms_provincias = []

    for entry in feed.entries:
        if provincia != None:
            if os.path.basename(entry.links[0].href).split('.')[3] == 'atom_{}'.format(str(provincia).zfill(2)):
                url = parseurl(entry.links[0].href)
                title = entry.title.value
                atoms_provincias.append((url, title))
        else:
            url = parseurl(entry.links[0].href)
            title = entry.title.value
            atoms_provincias.append((url, title))
    
    return atoms_provincias

@click.command()
@click.option('--provincia', '-p', default=None, type=click.INT, help='Código Gerencia Catastro. Si no se indica descarga todas las provincias.')
@click.option('--municipio', '-m', default=None, type=click.INT, help='Código Municipio Catastro. Si no se indica descarga todos los municipios.')
@click.option('--srs', default=None, type=click.INT, help='Código EPSG final. Si no se indica, se mantendrá el de origen.')
@click.option('--filename', default="buildings", help='Nombre Geopackage')
@click.option('--separar_salida', '-s', flag_value=True, is_flag=True, help='Separar salida a un GeoPackage por Provincia')
def cli(provincia=None, municipio=None, srs=None, filename="buildings", separar_salida=False):

    atoms_provincias = read_complete_atom(provincia)
    codmun = format_codmun(provincia, municipio) if municipio is not None else None

    geopackage_name = filename
    current_prov = 0
    total_prov = len(atoms_provincias)
    for atom in atoms_provincias:
        current_prov += 1
        prov_title = atom[1]
        prov_url = atom[0]
        print(prov_title)
        urls = read_prov_atom(prov_url, codmun=codmun)

        current_mun = 0
        total_mun = len(urls)
        for url in urls:
            current_mun += 1
            print('[{}/{}][{}/{}] Downloading {}'.format(current_prov, total_prov, current_mun, total_mun, url[0]))
            if separar_salida:
                geopackage_name = '_'.join([filename, prov_title.replace(' ', '_')])
            download_municipio(url[0], url[1], geopackage_name, to_epsg=srs)

if __name__ == '__main__':
    cli()