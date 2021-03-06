"""
Test that the various service reference implementations play well together.

Ref: https://github.com/VNG-Realisatie/gemma-zaken/issues/39
"""


import uuid
from base64 import b64encode

import requests
from zit.client import Client


def test_melding_overlast(text_file, png_file):
    ztc_client = Client('ztc')
    zrc_client = Client('zrc')
    orc_client = Client('orc')
    drc_client = Client('drc')

    # retrieve zaaktype/statustype from ZTC
    zaaktype = ztc_client.retrieve('zaaktype', catalogus_pk=1, id=1)
    status_type = ztc_client.retrieve('statustype', catalogus_pk=1, zaaktype_pk=1, id=1)
    assert status_type['url'] in zaaktype['statustypen']

    # registreer zaak
    zaak = zrc_client.create('zaak', {
        'zaaktype': zaaktype['url'],
        'registratiedatum': '2018-06-18',
        'toelichting': 'Hout van een boot is afgebroken en blokkeert de '
                       'linkerdoorgang van een brug.',
        'zaakgeometrie': 'POINT (4.910649523925713 52.37240093589432)',

    })
    zaak_id = zaak['url'].rsplit('/')[-1]
    assert 'url' in zaak

    # set status
    status = zrc_client.create('status', {
        'zaak': zaak['url'],
        'statusType': status_type['url'],
        'datumStatusGezet': '2018-06-18T15:11:33Z',
        'statustoelichting': 'Melding ontvangen',
    })

    zaak = zrc_client.retrieve('zaak', id=zaak_id)
    assert zaak['status'] == status['url']

    # assign address information
    verblijfsobject = orc_client.create('verblijfsobject', {
        'identificatie': uuid.uuid4().hex,
        'hoofdadres': {
            'straatnaam': 'Keizersgracht',
            'postcode': '1015 CJ',
            'woonplaatsnaam': 'Amsterdam',
            'huisnummer': '117',
        }
    })
    zaak_object = zrc_client.create('zaakobject', {
        'zaak': zaak['url'],
        'object': verblijfsobject['url'],
    })
    assert 'url' in zaak_object

    # Upload the files with POST /enkelvoudiginformatieobject (DRC)
    byte_content = text_file.read()  # text_file comes from pytest fixture
    base64_bytes = b64encode(byte_content)
    base64_string = base64_bytes.decode('utf-8')

    text_attachment = drc_client.create('enkelvoudiginformatieobject', {
        'identificatie': uuid.uuid4().hex,
        'bronorganisatie': '1',
        'creatiedatum': zaak['registratiedatum'],
        'titel': 'text_extra.txt',
        'auteur': 'anoniem',
        'formaat': 'text/plain',
        'taal': 'nl',
        'inhoud': base64_string
    })

    # Test if the EnkelvoudigInformatieObject stored has the right information
    assert 'creatiedatum' in text_attachment
    assert text_attachment['creatiedatum'] == zaak['registratiedatum']

    # Retrieve the EnkelvoudigInformatieObject
    txt_object_id = text_attachment['url'].rsplit('/')[-1]
    text_attachment = drc_client.retrieve('enkelvoudiginformatieobject', id=txt_object_id)

    # Test if the attached filed is our initial file
    assert requests.get(text_attachment['inhoud']).content == byte_content

    byte_content = png_file.getvalue()
    base64_bytes = b64encode(byte_content)
    base64_string = base64_bytes.decode('utf-8')

    image_attachment = drc_client.create('enkelvoudiginformatieobject', {
        'identificatie': uuid.uuid4().hex,
        'bronorganisatie': '1',
        'creatiedatum': zaak['registratiedatum'],
        'titel': 'afbeelding.png',
        'auteur': 'anoniem',
        'formaat': 'image/png',
        'taal': 'nl',
        'inhoud': base64_string
    })

    # Link the files to a 'Zaak' with POST /zaakinformatieobjecten (ZRC)
    zaakinformatieobject_1 = drc_client.create('zaakinformatieobject', {
        'zaak': zaak['url'],
        'informatieobject': text_attachment['url'],
    })
    assert 'url' in zaakinformatieobject_1

    zaakinformatieobject_2 = drc_client.create('zaakinformatieobject', {
        'zaak': zaak['url'],
        'informatieobject': image_attachment['url'],
    })
    informatie_object_id = zaakinformatieobject_2['url'].rsplit('/')[-1]

    # Test if it's possible to retrieve ZaakInformatieObject
    some_informatie_object = drc_client.retrieve('zaakinformatieobject', id=informatie_object_id)

    # Retrieve the EnkelvoudigInformatieObject from ZaakInformatieObject
    assert 'informatieobject' in some_informatie_object

    img_object_id = some_informatie_object['informatieobject'].rsplit('/')[-1]
    image_attachment = drc_client.retrieve('enkelvoudiginformatieobject', id=img_object_id)

    # Test if image correspond to our initial image
    assert requests.get(image_attachment['inhoud']).content == byte_content
