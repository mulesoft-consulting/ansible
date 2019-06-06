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
module: ap_exchange_application

short_description: Manage applications on Anypoint Exchange

version_added: "2.8"

description:
    - "This module supports management of applications at Master org level on Anypoint Exchange"

options:
    name:
        description:
            - Exchange application name
        required: true
    state:
        description:
            - Assert the state of the application. Use Use C(present) to create an application and C(absent) to delete it.
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
    description:
        description:
            - Exchange application description
        required: false
        default: false
        choices: [ "true", "false" ]
    url:
        description:
            - Exchange application URL
        required: false
        default: false
        choices: [ "true", "false" ]

author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
    - anypoint-cli
'''

EXAMPLES = '''
# Example of creating an application
- name: create an exchange application
  ap_exchange_application:
    name: 'My App'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    description: 'this is the app description'
    url: 'http://myapp-url.com'

# Example of deleting an application
- name: delete an exchange application
  ap_exchange_application:
    name: 'My App'
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
'''

RETURN = '''
app_id:
    description: Application id
    type: string
    returned: success
app_client_id:
    description: Application id
    type: string
    returned: success
app_client_secret:
    description: Application id
    type: string
    returned: success
msg:
    description: Anypoint CLI command output
    type: string
    returned: always
'''

import json
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url


def get_anypointcli_path(module):
    return module.get_bin_path('anypoint-cli', True, ['/usr/local/bin'])


def get_exchange_url(module, org_id):
    return 'https://' + module.params['host'] + '/exchange/api/v1/organizations/' + org_id


def execute_http_call(module, url, method, headers, payload):
    return_Value = None
    try:
        if (headers is not None):
            if (payload is not None):
                return_value = open_url(url, method=method, headers=headers, data=payload)
            else:
                return_value = open_url(url, method=method, headers=headers)

    except Exception as e:
        module.exit_json(msg=str(e))

    return return_value


def get_master_org_id(module):
    my_url = 'https://' + module.params['host'] + '/accounts/api/profile'
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}
    output = json.load(execute_http_call(module, my_url, 'GET', headers, None))

    return output['organization'].get('id')


def get_application_by_id(module, org_id, app_id):
    my_url = get_exchange_url(module, org_id) + '/applications/' + app_id
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}
    output = json.load(execute_http_call(module, my_url, 'GET', headers, None))
    print(output)

    return output


def get_existing_apps(module, org_id):
    my_url = get_exchange_url(module, org_id) + '/applications?query=&offset=0&limit=200'
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}

    return execute_http_call(module, my_url, 'GET', headers, None)


def do_no_action(module):
    return_value = dict(
        do_nothing=False,
        org_id=None,
        app_id=None,
        app_client_id=None,
        app_client_secret=None,
        app_update=False
    )
    app_exists = False
    url = None
    description = None

    return_value['org_id'] = get_master_org_id(module)
    app_list = json.load(get_existing_apps(module, return_value['org_id']))

    for item in app_list:
        if (item['name'] == module.params['name']):
            app_exists = True
            result = get_application_by_id(module, return_value['org_id'], str(item['id']))
            return_value['app_id'] = result['id']
            return_value['app_client_id'] = result['clientId']
            return_value['app_client_secret'] = result['clientSecret']
            url = item['url']
            description = item['description']
            break

    if (module.params['state'] == 'present'):
        if (return_value['app_id'] is None):
            # need to create the app
            return_value['do_nothing'] = False
        else:
            # need to update the app
            return_value['do_nothing'] = (module.params['url'] == url and module.params['description'] == description)
            return_value['app_update'] = not return_value['do_nothing']
    elif (module.params['state'] == 'absent'):
        return_value['do_nothing'] = (return_value['app_id'] is None)

    return return_value


def create_exchange_app(module, context):
    return_value = dict(
        output=None,
        app_id=None,
        app_client_id=None,
        app_client_secret=None
    )
    my_url = get_exchange_url(module, context['org_id']) + '/applications'
    headers = {
        'Authorization': 'Bearer ' + module.params['bearer'],
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    payload = {
        'name': module.params['name'],
        'description': module.params['description'],
        'url': module.params['url']
    }
    output = json.load(execute_http_call(module, my_url, 'POST', headers, json.dumps(payload)))
    context['app_id'] = str(output['id'])

    return_value['output'] = 'Application with id "' + context['app_id'] + '" created.'
    return_value['app_id'] = context['app_id']
    return_value['app_client_id'] = output['clientId']
    return_value['app_client_secret'] = output['clientSecret']

    return return_value


def update_exchange_app(module, context):
    return_value = dict(
        output=None,
        app_id=None,
        app_client_id=None,
        app_client_secret=None
    )
    my_url = get_exchange_url(module, context['org_id']) + '/applications'
    headers = {
        'Authorization': 'Bearer ' + module.params['bearer'],
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    payload = {
        'name': module.params['name'],
        'description': module.params['description'],
        'url': module.params['url']
    }
    output = json.load(execute_http_call(module, my_url, 'PATCH', headers, json.dumps(payload)))
    context['app_id'] = str(output['id'])

    return_value['output'] = 'Application with id "' + context['app_id'] + '" updated.'
    return_value['app_id'] = context['app_id']
    return_value['app_client_id'] = output['clientId']
    return_value['app_client_secret'] = output['clientSecret']

    return return_value


def delete_exchange_app(module, context):
    return_value = dict(
        output=None,
        app_id=None,
        app_client_id=None,
        app_client_secret=None
    )
    my_url = get_exchange_url(module, context['org_id']) + '/applications/' + context['app_id']
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}

    execute_http_call(module, my_url, 'DELETE', headers, None)
    return_value['output'] = 'Application with id "' + context['app_id'] + '" deleted.'

    return return_value


def create_or_update_exchange_app(module, context):
    return False


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "absent"]),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        description=dict(type='str', required=False),
        url=dict(type='str', required=False)
    )

    result = dict(
        changed=False,
        msg='No action taken',
        app_id=None,
        app_client_id=None,
        app_client_secret=None
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Main Module Logic
    # first all check that the anypoint-cli binary is present on the host
    if (get_anypointcli_path(module) is None):
        module.fail_json(msg="anypoint-cli binary not present on host")

    # exit if the execution is in check_mode
    if module.check_mode:
        module.exit_json(**result)

    # exit if I need to do nothing, so check if environment exists
    context = do_no_action(module)
    result['app_id'] = context['app_id']
    result['app_client_id'] = context['app_client_id']
    result['app_client_secret'] = context['app_client_secret']

    if (context['do_nothing'] is True):
        module.exit_json(**result)

    if (module.params['state'] == 'present'):
        if (context['app_update'] is True):
            output = update_exchange_app(module, context)
        else:
            output = create_exchange_app(module, context)
    elif (module.params['state'] == 'absent'):
        output = delete_exchange_app(module, context)

    result['changed'] = True
    result['app_id'] = output['app_id']
    result['app_client_id'] = output['app_client_id']
    result['app_client_secret'] = output['app_client_secret']
    result['msg'] = output
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
