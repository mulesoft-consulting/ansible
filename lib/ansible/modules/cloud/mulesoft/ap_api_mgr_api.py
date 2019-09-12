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
module: ap_api_mgr_api

short_description: Manage APIs on API Manager

version_added: "2.8"

description:
    - "This module supports basic operations for create or delete APIs on Anypoint Platform API Manager"

options:
    name:
        description:
            - The assets assetId in Exchange
        required: true
    state:
        description:
            - Assert the state of the managed API. Use C(present) to create an API, C(deprecated) to deprecate it and C(absent) to delete it.
        required: true
        choices: [ "present", "deprecated", absent" ]
    asset_version:
        description:
            - The assets version in Exchange
        required: true
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
    environment:
        description:
            - Environment on the Business Group to work on
        required: false
        default: Sandbox
    type:
        description:
            - Endpoint type
        choices: [ "http", "raml", "wsdl" ]
        default: raml
        required: false
    with_proxy:
        description:
            - Indicates whether the endpoint should use a proxy
        required: false
        default: false
    references_user_domain:
        description:
            - Indicates whether a proxy should reference a user domain
        required: false
        defualt: false
    mule_4:
        description:
            - Indicates whether you are managing this API in Mule 4 or above
        required: false
        default: true
    deployment_type:
        description:
            - deloyment type
        choices: [ "cloudhub", "hybrid", "rtf" ]
        default: cloudhub
    uri:
        description:
            - Implementation URI
        required: false
    response_timeout:
        description:
            - Response timeout
        required: false
    instance_label:
        description:
            - API instance label
        required: false
    proxy:
        description:
            - represents the proxy of the API if any
        suboptions:
            scheme:
                description:
                    - proxy scheme
                choices: [ "http", "https" ]
                required: false
            port:
                description:
                    - proxy port
                required: false
            path:
                description:
                    - proxy path
                required: false
    wsdl:
        description:
            - describes sttributes related to the WSDL if the API is one
        suboptions:
            name:
                description:
                    - WSDL service name
                required: false
            namespace:
                description:
                    - WSDL service namespace
                required: false
            port:
                description:
                    - WSDL service port
                required: false


author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
    - anypoint-cli
'''

EXAMPLES = '''
# Example of managing a new API
- name: Manage API
  ap_api_mgr_api:
    name: 'sapi-notification-saas'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    host: anypoint.mulesoft.com
    organization: 'My Demos'
    environment: 'Sandbox'
    asset_version: '1.0.1'
    type: 'raml'
    instance_label: 'My API from Ansible'

# Example of a deleting a managed API
- name: Delete API
  ap_api_mgr_api:
    name: 'sapi-notification-saas'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    host: anypoint.mulesoft.com
    organization: 'My Demos'
    environment: 'Sandbox'
    asset_version: '1.0.1'
'''

RETURN = '''
api_instance_id:
    description: API Instance ID
    type: string
    returned: always
msg:
    description: Anypoint CLI command output
    type: string
    returned: always
'''

import json
import re
from ansible.module_utils.basic import AnsibleModule


def get_anypointcli_path(module):
    return module.get_bin_path('anypoint-cli', True, ['/usr/local/bin'])


def check_if_update_needed(module, cmd_base, api_instance_id):
    return_value = False
    not_found_regex = '^Error: API with ID "[0-9]{5,}" not found in environment ID' \
                      '"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"'
    cmd_final = cmd_base
    cmd_final += ' describe ' + api_instance_id + ' --output json'

    result = module.run_command(cmd_final)

    if result[0] != 0:
        module.fail_json(msg=result[1])

    resp_json = json.loads(result[1])
    # validate field by field
    if (resp_json.get('Instance Label') is None and module.params['instance_label'] is not None):
        return_value = True
    elif (resp_json.get('Deprecated') == 'Y'):
        # this doesn't work, actually anypoint-cli is always returning 'N'
        # https://www.mulesoft.org/jira/browse/APC-22
        return_value = True
    elif (resp_json.get('Implementation URI') is None and module.params['uri'] is not None):
        return True
    elif (resp_json.get('Proxy URI') is None and module.params['with_proxy'] is True):
        return True

    return return_value


def get_context(module, cmd_base):
    return_value = dict(
        do_nothing=False,
        api_managed=False,
        api_deprecated=False,
        api_instance_id=None
    )
    cmd_final = cmd_base
    cmd_final += ' list --output json'

    result = module.run_command(cmd_final)

    if result[0] != 0:
        module.fail_json(msg=result[1])

    if not result[1].strip():
        return return_value

    resp_json = json.loads(result[1])
    # check if the API is already managed
    for item in resp_json:
        if (item['Asset ID'] == module.params['name']) and (item['Asset Version'] == module.params['asset_version']):
            return_value['api_managed'] = True
            return_value['api_deprecated'] = (item['Deprecated'] == 'Y')
            return_value['api_instance_id'] = str(item['Instance ID'])

    if (module.params['state'] == "present"):
        if (return_value['api_managed'] is True):
            return_value['do_nothing'] = not check_if_update_needed(module, cmd_base, return_value['api_instance_id'])
    elif (module.params['state'] == "deprecated"):
        return_value['do_nothing'] = (return_value['api_managed'] is True and return_value['api_deprecated'] is True)
    elif (module.params['state'] == "absent"):
        return_value['do_nothing'] = (return_value['api_managed'] is False)

    return return_value


def create_update_api(module, cmd_base, context):
    return_value = dict(
        output='',
        api_instance_id=None
    )
    # add all the required options
    options = ' --type ' + module.params['type']
    if (module.params['with_proxy'] is True):
        options += ' --withProxy'
    if (module.params['references_user_domain'] is True):
        options += ' --referencesUserDomain'
    if (module.params['mule_4'] is True):
        options += ' --muleVersion4OrAbove '
    options += ' --deploymentType "' + module.params['deployment_type'] + '"'
    if (module.params['uri'] is not None):
        options += ' --uri "' + + module.params['uri'] + '"'
    if (module.params['response_timeout'] is not None):
        options += ' --response_timeout "' + module.params['response_timeout'] + '"'
    if (module.params['instance_label'] is not None):
        options += ' --apiInstanceLabel "' + module.params['instance_label'] + '"'
    # proxy args
    if (module.params['proxy'] is not None
            and module.params['proxy']['scheme'] is not None
            and module.params['proxy']['port'] is not None
            and module.params['proxy']['path'] is not None):
        options += ' --scheme "' + module.params['proxy']['scheme'] + '"'
        options += ' --port "' + module.params['proxy']['port'] + '"'
        options += ' --path "' + module.params['proxy']['path'] + '"'
    # wsdl args
    if (module.params['wsdl'] is not None
            and module.params['wsdl']['name'] is not None
            and module.params['wsdl']['namespace'] is not None
            and module.params['wsdl']['port'] is not None):
        options += ' --serviceName "' + module.params['wsdl']['name'] + '"'
        options += ' --serviceNamespace  "' + + module.params['wsdl']['namespace'] + '"'
        options += ' --servicePort "' + module.params['wsdl']['port'] + '"'

    cmd_final = cmd_base
    # deterimine if need to manage the API or edit it
    if (context['api_managed'] is True):
        # edit existing managed api
        # First undeprecate api if it is necessary
        if (context['api_deprecated'] is True):
            cmd_final += ' undeprecate "' + context['api_instance_id'] + '"'
            undeprecate_api(module, cmd_base, context)
            cmd_final = cmd_base

        cmd_final += ' edit ' + options + '"' + context['api_instance_id'] + '"'
        return_value['api_instance_id'] = context['api_instance_id']
    else:
        # manage new api asset_id and asset_version
        options += ' "' + module.params['name'] + '"'
        options += ' "' + module.params['asset_version'] + '"'
        cmd_final += ' manage ' + options
    # finally execute either manage or edit
    result = module.run_command(cmd_final)

    if result[0] != 0:
        module.fail_json(msg=result[1])

    return_value['output'] = result[1].replace('\n', '')
    # get api_instance_id only on creation
    if (context['api_managed'] is False):
        temp = return_value['output'].replace('Created new API with ID: ', '')
        return_value['api_instance_id'] = temp.replace('\n', '')

    return return_value


def undeprecate_api(module, cmd_base, context):
    cmd_final = cmd_base
    cmd_final += ' undeprecate'
    cmd_final += ' "' + context['api_instance_id'] + '"'
    result = module.run_command(cmd_final)

    if result[0] != 0:
        module.fail_json(msg=result[1])

    return result[1]


def deprecate_api(module, cmd_base, context):
    return_value = dict(
        output='',
        api_instance_id=context['api_instance_id']
    )
    cmd_final = cmd_base
    cmd_final += ' deprecate'
    cmd_final += ' "' + context['api_instance_id'] + '"'
    result = module.run_command(cmd_final)

    if result[0] != 0:
        module.fail_json(msg=result[1])
    return_value['output'] = result[1]

    return return_value


def delete_api(module, cmd_base, context):
    return_value = dict(
        output='',
        api_instance_id=context['api_instance_id']
    )
    cmd_final = cmd_base
    cmd_final += ' delete'
    cmd_final += ' "' + context['api_instance_id'] + '"'
    result = module.run_command(cmd_final)

    if result[0] != 0:
        module.fail_json(msg=result[1])
    return_value['output'] = result[1].replace('\n', '')

    return return_value


def run_module():
    # define specs
    proxy_spec = dict(
        scheme=dict(type='str', required=False, choices=['http', 'https']),
        port=dict(type='str', required=False),
        path=dict(type='str', required=False)
    )

    wsdl_spec = dict(
        name=dict(type='str', required=False),
        namespace=dict(type='str', required=False),
        port=dict(type='str', required=False)
    )
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=['present', 'deprecated', 'absent']),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization=dict(type='str', required=True),
        environment=dict(type='str', required=False, default='Sandbox'),
        asset_version=dict(type='str', required=True),
        type=dict(type='str', required=False, default="raml", choices=["http", "raml", "wsdl"]),
        with_proxy=dict(type='bool', required=False, default=False),
        references_user_domain=dict(type='bool', required=False, default=False),
        mule_4=dict(type='bool', required=False, default=True),
        deployment_type=dict(type='str', required=False, default='cloudhub', choices=["cloudhub", "hybrid", "rtf"]),
        uri=dict(type='str', required=False),
        response_timeout=dict(type='int', required=False),
        instance_label=dict(type='str', required=False),
        proxy=dict(type='dict', options=proxy_spec),
        wsdl=dict(type='dict', options=wsdl_spec)
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

    cmd = get_anypointcli_path(module) + ' --bearer="' + module.params['bearer'] + '"'
    cmd += ' --host="' + module.params['host'] + '"'
    cmd += ' --organization="' + module.params['organization'] + '"'
    cmd += ' --environment="' + module.params['environment'] + '"'
    cmd += ' api-mgr api'
    cmd_base = cmd

    # exit if I need to do nothing
    context = get_context(module, cmd_base)
    result['api_instance_id'] = context['api_instance_id']

    if (context['do_nothing'] is True):
        module.exit_json(**result)

    # Parameters set & validation
    if (module.params['state'] == 'present') and (module.params['with_proxy'] is True):
        if ((module.params['proxy']['scheme'] is None)
                or (module.params['proxy']['port'] is None)
                or (module.params['proxy']['path'] is None)):
            module.fail_json(msg="you need to specify proxy.scheme, proxy.port and proxy.path for present state and with_proxy option")

    if (module.params['state'] == 'present') and (module.params['type'] == 'wsdl'):
        if ((module.params['wsdl']['name'] is None)
                or (module.params['wsdl']['namespace'] is None)
                or (module.params['wsdl']['port'] is None)):
            module.fail_json(msg="you need to specify wsdl.name, wsdl.namespace and wsdl.port for present state and type wsdl")

    # check mode
    if module.check_mode:
        module.exit_json(**result)

    # Finally, execute some stuff
    if module.params['state'] == "present":
        op_result = create_update_api(module, cmd_base, context)
    elif module.params['state'] == "deprecated":
        op_result = deprecate_api(module, cmd_base, context)
    elif module.params['state'] == "absent":
        op_result = delete_api(module, cmd_base, context)

    result['msg'] = op_result['output']
    result['api_instance_id'] = op_result['api_instance_id']
    result['changed'] = True

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
