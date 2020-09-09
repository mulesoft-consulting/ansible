#!/usr/bin/python

# Copyright: (c) 2020, Gonzalo Camino <gonzalo.camino@mulesoft.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import json
import os
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.cloud.anypoint import ap_common
from ansible.module_utils.urls import open_url
from ansible.module_utils.six.moves.urllib.parse import urlencode

def get_asset_identifier(group_id, asset_id, asset_version):
    return group_id + '/' + asset_id + '/' + asset_version


def get_exchange_v1_url(module, group_id, asset_id, asset_version, need_version):
    url = 'https://' + module.params['host'] + '/exchange/api/v1/organizations/' + module.params['organization_id'] + '/assets/'
    if (need_version is True):
        url += get_asset_identifier(group_id, asset_id, asset_version)
    else:
        url += group_id + '/' + asset_id
    return url


def get_exchange_v2_url(module, group_id, asset_id, asset_version, need_version):
    url = 'https://' + module.params['host'] + '/exchange/api/v2/assets/'
    if (need_version is True):
        url += get_asset_identifier(group_id, asset_id, asset_version)
    else:
        url += group_id + '/' + asset_id
    return url


def get_graphql_v1_url(host):
    return 'https://' + host + '/graph/api/v1/graphql'


def look_exchange_asset_with_graphql(module, group_id, asset_id, asset_version):
    my_url = get_graphql_v1_url(module.params['host'])
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }
    payload = {
        'query': '{assets(asset: {groupId: "' + group_id + '",'
                 'assetId: "' + asset_id + '",'
                 'version: "' + asset_version + '"'
                 '}){assetId groupId version type name}}'
    }

    return ap_common.execute_http_call('[look_exchange_asset_with_graphql]', module, my_url, 'POST', headers, payload)


def analyze_asset(module, group_id, asset_id, asset_version, name, description, icon, tags):
    return_value = dict(
        must_update=False,
        must_update_name=False,
        must_update_icon=False,
        must_update_description=False,
        must_update_tags=False,
        deprecated=False
    )
    my_url = get_exchange_v2_url(module, group_id, asset_id, asset_version, True)
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}

    resp_json = ap_common.execute_http_call('[analyze_asset]', module, my_url, 'GET', headers, None)

    if (resp_json['status'] == 'deprecated'):
        return_value['deprecated'] = True

    if ((name is not None) and (name != resp_json['name'])):
        return_value['must_update_name'] = True

    if (tags != resp_json['labels']):
        return_value['must_update_tags'] = True

    if (description != resp_json['description']):
        return_value['must_update_description'] = True

    # check if icon needs to be changed
    #for item in resp_json['files']:
    #    if (item['classifier'] == 'icon'):
    #        icon_md5 = module.md5(icon)
    #        if (icon_md5 == item['md5']):
    #            return_value['must_update'] = False
    #            break
    actual_icon = None
    for item in resp_json['files']:
        if (item['classifier'] == 'icon'):
            actual_icon = item
            break
    if (((actual_icon is None) and (icon is not None))
            or (actual_icon is not None) and (icon is None)):
        return_value['must_update_icon'] = True
    else:
        # there is an icon on exchange and and icon is specified on the module
        # so I need to check if images are the same or not
        if ((actual_icon is not None) and (icon is not None)):
            icon_md5 = module.md5(icon)
            if (icon_md5 == item['md5']):
                return_value['must_update_icon'] = True

    return_value['must_update'] = (return_value['must_update_description'] is True 
        or return_value['must_update_icon'] is True 
        or return_value['must_update_tags'] is True
        or return_value['must_update_name'] is True)

    return return_value


def modify_exchange_asset(module, group_id, asset_id, asset_version, context, name, description, icon, tags):
    if (context['exchange_must_update_tags'] is True):
        set_asset_tags(module, group_id, asset_id, asset_version, tags)
    if (context['exchange_must_update_description'] is True):
        set_asset_description(module, group_id, asset_id, asset_version, description)
    if (context['exchange_must_update_icon'] is True):
        set_asset_icon(module, group_id, asset_id, asset_version, icon)
    if (context['exchange_must_update_name'] is True):
        set_asset_name(module, group_id, asset_id, asset_version, name)

    return "Asset modified"


def set_asset_tags(module, group_id, asset_id, asset_version, tags):
    my_url = get_exchange_v1_url(module, group_id, asset_id, asset_version, True)
    my_url += '/tags'
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }
    payload = []
    desired_tags = tags
    json_payload = []
    if (desired_tags):
        for tag in desired_tags:
            payload.append({'value': tag})
        json_payload = payload
    else:
        json_payload = []

    ap_common.execute_http_call('[set_asset_tags]', module, my_url, 'PUT', headers, json_payload)

    return 'Asset modified'


def set_asset_name(module, group_id, asset_id, asset_version, name):
    my_url = get_exchange_v2_url(module, group_id, asset_id, asset_version, False)
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }
    payload = {
        'name': name
    }

    output = ap_common.execute_http_call('[set_asset_name]', module, my_url, 'PATCH', headers, payload)

    return output


def set_asset_description(module, group_id, asset_id, asset_version, description):
    my_url = get_exchange_v2_url(module, group_id, asset_id, asset_version, False)
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }
    tmp_desc = description
    if (tmp_desc is None):
        tmp_desc = ''
    payload = {
        'description': tmp_desc
    }

    output = ap_common.execute_http_call('[set_asset_description]', module, my_url, 'PATCH', headers, payload)

    return output


def set_asset_icon(module, group_id, asset_id, asset_version, icon):
    my_url = get_exchange_v2_url(module, group_id, asset_id, asset_version, False) + '/icon'
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }
    if (icon is None):
        # delete the icon
        ap_common.execute_http_call('[set_asset_icon]', module, my_url, 'DELETE', headers, None)
        output = 'Asset icon deleted (if any)'
    else:
        icon_extension = os.path.splitext(icon)[1]
        if (icon_extension == '.png') or (icon_extension == '.jpeg') or (icon_extension == '.jpg'):
            headers.update({'Content-Type': 'image/png'})
        elif (icon_extension == '.svg'):
            headers.update({'Content-Type': 'image/svg+xml'})
        else:
            module.fail_json(msg=('[set_asset_icon] Unsupported extension [' + icon_extension + ']. Supported ones: svg, png, jpg, jpeg'))
        f = open(icon, 'rb')
        payload = f.read()
        f.close()
        try:
            output = open_url(my_url, method='PUT', headers=headers, data=payload)
            output = 'Asset icon updated'
        except Exception as e:
            module.fail_json(msg='[set_asset_icon] Error updating icon' + ' [' + str(e) + ']')
        

    return output


def delete_exchange_asset(module, group_id, asset_id, asset_version):
    my_url = get_exchange_v1_url(module, group_id, asset_id, asset_version, True)
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}
    ap_common.execute_http_call('[delete_exchange_asset]', module, my_url, 'DELETE', headers, None)

    return 'Asset deleted'