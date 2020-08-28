#!/usr/bin/python

# Copyright: (c) 2019, Gonzalo Camino <gonzalo.camino@mulesoft.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: ap_exchange_asset_resource

short_description: Manage a Resource of an Asset on Exchange

version_added: "2.8"

description:
    - "This module supports upload and delete assets resources on Exchange"

options:
    name:
        description:
            - Resource name. This name does not include the UUID added by the Exchange API.
    state:
        description:
            - Assert the state of the page. Use C(present) to create a page and C(absent) to delete it.
        required: true
        choices: [ "present", "absent" ]
    bearer:
        description:
            - Anypoint Platform access token for an active session
        required: true
    host:
        description:
            - The host of your Anypoint Platform Installation
        required: false
        default: anypoint.mulesoft.com
    organization:
        description:
            - Anypoint Platform Organization Name to work on
        required: true
    group_id:
        description:
            - The assets groupId
        required: true
    asset_id:
        description:
            - The assets assetId
        required: true
    asset_version:
        description:
            - The assets version
        required: false
        default: 1.0.0
    path:
        description:
            - Path to the resource file. It is required for C(present)

author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
   - requests
'''

EXAMPLES = '''
# Example of setting exchange asset main page
- name: Upload Exchange Asset Resource
  ap_exchange_asset_resource:
    name: 'home'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    group_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    asset_id: 'my-fragment'
    asset_version: '1.0.1'
    path: '/tmp/photo.jpg'

# Example of deleting exchange asset main page
- name: Delete Exchange sset Resource
  ap_exchange_asset_resource:
    name: 'home'
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    group_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    asset_id: 'my-fragment'
    asset_version: '1.0.1'
'''

RETURN = '''
url:
    description: URL to asset resource
    type: str
    returned: always
msg:
    description: Anypoint CLI command output
    type: str
    returned: always
'''

import json
import os
import importlib
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.basic import missing_required_lib
from ansible.module_utils.urls import open_url
from ansible.module_utils.cloud.anypoint import ap_common
from ansible.module_utils.cloud.anypoint import ap_account_common
from ansible.module_utils.cloud.anypoint import ap_exchange_common
import traceback
LIB_IMP_ERR = None
try:
    import requests
    HAS_LIB = True
except Exception:
    HAS_LIB = False
    LIB_IMP_ERR = traceback.format_exc()


def get_exchange_asset_portal_url(module):
    url = ap_exchange_common.get_exchange_v2_url(module, module.params['group_id'], module.params['asset_id'], module.params['asset_version'], True)
    url += '/portal/draft'
    return url


def remove_uuid_from_resource_name(name):
    name_without_extension = os.path.splitext(name)[0]
    name_extension = os.path.splitext(name)[1]
    final_index = len(name_without_extension) - 37
    original_name = name_without_extension[0:final_index] + name_extension
    # also replace '%' characters because it causes a different name after the resource upload
    original_name.replace(r'%', '')

    return original_name


def get_context(module):
    return_value = dict(
        do_nothing=False,
        resource_url=None
    )

    my_url = get_exchange_asset_portal_url(module) + '/resources'
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}

    resp_json = ap_common.execute_http_call('[get_context]', module, my_url, 'GET', headers, None)

    # check if asset's resource exists
    for item in resp_json:
        resource_name = remove_uuid_from_resource_name(item['path'].replace('resources/', ''))
        if (resource_name == module.params['name']):
            return_value['resource_url'] = item['path']

    if (module.params['state'] == "present"):
        return_value['do_nothing'] = (return_value['resource_url'] is not None)
    elif (module.params['state'] == "absent"):
        return_value['do_nothing'] = (return_value['resource_url'] is None)

    return return_value


def create_resource(module):
    return_value = dict(
        msg='Resource created',
        resource_url=None
    )
    portal_resources_url = get_exchange_asset_portal_url(module) + '/resources'
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }
    # if the resource name contains '%', I just remove it becuase it causes troubles at resource upload time
    image_filename = os.path.basename(module.params['path']).replace(r'%', '')
    data = {
        'data': (image_filename, open(module.params['path'], 'rb'), 'image/png')
    }

    try:
        r = requests.Request('POST', portal_resources_url, files=data, headers=headers)
        prepared = r.prepare()
        s = requests.Session()
        resp = s.send(prepared)
        resp_json = json.loads(resp.text)
        return_value['resource_url'] = resp_json["path"]
    except Exception as e:
        resp_error = {
            'body': resp_json,
            'headers': resp.headers
        }
        module.fail_json(msg='[create_resource] ' + str(resp_error))

    return return_value


def delete_resource(module, resource_url):
    return_value = dict(
        msg='Resource deleted',
        resource_url=None
    )
    my_url = get_exchange_asset_portal_url(module) + '/' + resource_url
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}

    ap_common.execute_http_call('[delete_resource]', module, my_url, 'DELETE', headers, None)

    return return_value


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "absent"]),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization=dict(type='str', required=True),
        group_id=dict(type='str', required=True),
        asset_id=dict(type='str', required=True),
        asset_version=dict(type='str', required=False, default="1.0.0"),
        path=dict(type='str', required=False)
    )
    result = dict(
        changed=False,
        url=None,
        msg='No action taken'
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )
    if not HAS_LIB:
        module.fail_json(msg=missing_required_lib("requests"), exception=LIB_IMP_ERR)
    # Main Module Logic

    # validations pre check_mode
    if (module.params['state'] == 'present') and (module.params['path'] is None):
        module.fail_json(msg="present state requires 'path' argument")

    if module.check_mode:
        module.exit_json(**result)

    # exit if I need to do nothing, so check if environment exists
    context = get_context(module)
    result['url'] = context['resource_url']
    if (context['do_nothing'] is True):
        module.exit_json(**result)

    output = None
    if (module.params['state'] == 'present'):
        output = create_resource(module)
    elif (module.params['state'] == 'absent'):
        output = delete_resource(module, result['url'])

    result['msg'] = output['msg']
    result['url'] = output['resource_url']
    result['changed'] = True

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
