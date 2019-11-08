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
module: ap_exchange_asset_page

short_description: Manage the Page of an Asset on Exchange

version_added: "2.8"

description:
    - "This module supports upload, modify and delete assets pages on Exchange"

options:
    name:
        description:
            - Asset page name. Naming the page [home] makes the uploaded page the main description page for the Exchange asset
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
    md_path:
        description:
            - Path to the markdown page file. Required for C(present)

author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
   - anypoint-cli
'''

EXAMPLES = '''
# Example of setting exchange asset main page
- name: Upload Exchange Page
  ap_exchange_asset_page:
    name: 'home'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    group_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    asset_id: 'my-fragment'
    asset_version: '1.0.1'
    md_path: '/tmp/home.md'

# Example of deleting exchange asset main page
- name: Delete Exchange Page
  ap_exchange_asset_page:
    name: 'home'
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    group_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    asset_id: 'my-fragment'
    asset_version: '1.0.1'
'''

RETURN = '''
msg:
    description: Anypoint CLI command output
    type: str
    returned: always
'''

import json
import fileinput
import re
import os
import uuid
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url


def get_anypointcli_path(module):
    return module.get_bin_path('anypoint-cli', True, ['/usr/local/bin'])


def get_asset_identifier(group_id, asset_id, asset_version):
    return group_id + '/' + asset_id + '/' + asset_version


def get_exchange_url(module):
    url = 'https://' + module.params['host'] + '/exchange/api/v2/assets/'
    url += get_asset_identifier(module.params['group_id'], module.params['asset_id'], module.params['asset_version']) + '/portal/draft'
    return url


def execute_http_call(module, url, method, headers, payload):
    return_value = None
    try:
        if (headers is not None):
            if (payload is not None):
                return_value = open_url(url, method=method, headers=headers, data=payload)
            else:
                return_value = open_url(url, method=method, headers=headers)

    except Exception as e:
        module.fail_json(msg=str(e))

    return return_value


def get_asset_resources(module):
    my_url = get_exchange_url(module) + '/resources'
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}

    output = execute_http_call(module, my_url, 'GET', headers, None)
    resp_json = json.loads(output.read())
    return resp_json


def remove_uuid_from_resource_name(name):
    name_without_extension = os.path.splitext(name)[0]
    name_extension = os.path.splitext(name)[1]
    final_index = len(name_without_extension) - 37
    original_name = name_without_extension[0:final_index] + name_extension

    return original_name


def execute_anypoint_command(module, action, other_args):
    asset_identifier = get_asset_identifier(module.params['group_id'], module.params['asset_id'], module.params['asset_version'])
    cmd = get_anypointcli_path(module) + ' --bearer="' + module.params['bearer'] + '"'
    cmd += ' --host="' + module.params['host'] + '"'
    cmd += ' --organization="' + module.params['organization'] + '"'
    cmd += ' exchange asset page ' + action + ' "' + asset_identifier + '"' + other_args + ' --output json'

    output = module.run_command(cmd)

    if output[0] != 0:
        module.fail_json(msg='[execute_anypoint_command] ' + output[1])

    return output[1]


def replace_resource_names(module, filedata):
    resource_regex = r'!\[resources\/.*\]'
    resources_uploaded = get_asset_resources(module)
    page_resources_to_replace = re.findall(resource_regex, filedata)
    for ocurrence in page_resources_to_replace:
        # here I expect a string like "![resources/chalo-2b5affd5-2584-4ccc-a46a-68aeb77806b5.jpg]""
        resource_name = ocurrence.replace('![', '').replace(']', '')
        #raw_resource_name = remove_uuid_from_resource_name(resource_name.replace('resources/', ''))
        raw_resource_name = resource_name.replace('resources/', '')
        for uploaded_resource in resources_uploaded:
            tmp = remove_uuid_from_resource_name(uploaded_resource['path'].replace('resources/', ''))
            if (tmp == raw_resource_name):
                filedata = filedata.replace(resource_name, uploaded_resource['path'])
                break

    return filedata


def page_content_must_change(module):
    # read data from existing object
    try:
        tmp_dir = '/tmp/' + module.md5(module.params['md_path'])
    except Exception as e:
        module.fail_json(msg="[page_content_must_change] Error reading file %s" % module.params['md_path'])

    try:
    
        os.mkdir(tmp_dir)
    except Exception as e:
        module.fail_json(msg="[page_content_must_change] Creation of the directory %s failed" % tmp_dir)

    execute_anypoint_command(module, 'download', ' "' + tmp_dir + '" "' + module.params['name'] + '"')

    downloaded_file = tmp_dir + '/' + module.params['name'] + '.md'
    f = open(downloaded_file, 'r')
    actual_data = f.read()
    f.close()
    # delete file and directory
    try:
        os.remove(downloaded_file)
        os.rmdir(tmp_dir)
    except Exception as e:
        module.fail_json(msg="[page_content_must_change] Deletion of the directory %s failed" % tmp_dir)

    # read data from specified resource
    f = open(module.params['md_path'], 'r')
    file_data = f.read()
    f.close()
    file_data = replace_resource_names(module, file_data)

    return (actual_data != file_data)


def get_context(module):
    return_value = dict(
        do_nothing=False,
        resource_url=None
    )
    page_exists = False

    output = execute_anypoint_command(module, 'list', '')

    cleaned_result = output.replace('Getting asset pages list', '')
    if (len(cleaned_result) > 2):
        resp_json = json.loads(cleaned_result)
        # check if the asset's page exists
        for item in resp_json:
            if (item['Name'] == module.params['name']):
                page_exists = True

    if (module.params['state'] == "present"):
        if (page_exists is True):
            return_value['do_nothing'] = not (page_content_must_change(module) is True)
    elif (module.params['state'] == "absent"):
        return_value['do_nothing'] = not page_exists

    return return_value


def replace_resources_on_file(module, file_name):
    # open file to work with
    f = open(file_name, 'r')
    filedata = f.read()
    f.close()
    # replace content
    filedata = replace_resource_names(module, filedata)
    # finally write file content
    f = open(file_name, 'w')
    f.write(filedata)
    f.close()

    return True


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
        md_path=dict(type='str', required=False, default=None)
    )
    result = dict(
        changed=False,
        msg='No action taken'
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Main Module Logic
    # first all check that the anypoint-cli binary is present on the host
    if (get_anypointcli_path(module) is None):
        module.fail_json(msg="anypoint-cli binary not present on host")

    # validations pre check_mode
    if (module.params['state'] == 'present') and (module.params['md_path'] is None):
        module.fail_json(msg="present state requires 'md_path' argument")

    if module.check_mode:
        module.exit_json(**result)

    # exit if I need to do nothing, so check if environment exists
    context = get_context(module)
    if (context['do_nothing'] is True):
        module.exit_json(**result)

    other_args = " '" + module.params['name'] + "'"
    if (module.params['state'] == 'present'):
        action = 'upload'
        new_path = '/tmp/' + module.md5(module.params['md_path']) + "_" + os.path.basename(module.params['md_path'])
        module.preserved_copy(module.params['md_path'], new_path)
        output = replace_resources_on_file(module, new_path)
        other_args += " '" + new_path + "'"
    elif (module.params['state'] == 'absent'):
        action = 'delete'

    output = execute_anypoint_command(module, action, other_args)

    result['msg'] = output
    result['changed'] = True

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
