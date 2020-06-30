#!/usr/bin/python

# Copyright: (c) 2020, Gonzalo Camino <gonzalo.camino@mulesoft.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import json
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.cloud.anypoint import ap_common
from ansible.module_utils.urls import open_url
from ansible.module_utils.six.moves.urllib.parse import urlencode

def get_organization_client_secret(module, org_id, client_id):
    return_value = None
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/organizations/' + org_id + '/clients/' + client_id
    my_url = server_name + api_endpoint

    headers = {
        'Accept': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }

    resp_json = ap_common.execute_http_call('[get_organization_client_secret]', module, my_url, 'GET', headers, None)
    return_value = resp_json['client_secret']

    return return_value


def get_organization(module, org_id):
    return_value = None
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/organizations/' + org_id
    my_url = server_name + api_endpoint

    headers = {
        'Accept': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }
    return_value = ap_common.execute_http_call('[get_organization]', module, my_url, 'GET', headers, None)

    return return_value


def get_me(module):
    return_value = None
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/me'
    my_url = server_name + api_endpoint

    headers = {
        'Accept': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }

    return_value = ap_common.execute_http_call('[get_me]', module, my_url, 'GET', headers, None)

    return return_value


def get_organizations_list(module):
    return_value = None
    resp_json = get_me(module)
    return_value = resp_json['user']['memberOfOrganizations']

    return return_value


def get_organization_id(module, org_name):
    org_id = None
    output = get_user_profile(module)
    for item in output['memberOfOrganizations']:
        if (item['name'] == org_name):
            org_id = item['id']
            break
    if (org_id is None):
        module.fail_json(msg='Organization with name {' + org_name + '} not found')

    return org_id


def get_organization_name(module, org_id):
    organization = get_organization(module, org_id)

    return organization['name']


def get_user_profile(module):
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/profile'
    my_url = server_name + api_endpoint
    headers = {
        'Accept': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }
    return_value = ap_common.execute_http_call('[get_user_profile]', module, my_url, 'GET', headers, None)

    return return_value


def get_users_list(module, org_id, deleted):
    return_value = None
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/organizations/' + org_id + '/users?deleted=' + str(deleted)
    my_url = server_name + api_endpoint

    headers = {
        'Accept': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }

    resp_json = ap_common.execute_http_call('[get_users_list]', module, my_url, 'GET', headers, None)
    return_value = resp_json['data']

    return return_value