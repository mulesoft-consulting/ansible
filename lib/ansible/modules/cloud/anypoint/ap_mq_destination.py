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
module: ap_mq_destination

short_description: Manage Destinations on Anypoint MQ

version_added: "2.8"

description:
    - "This module supports management of destinations at Environment level on Anypoint MQ"

options:
    name:
        description:
            - MQ destination name
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
    organization:
        description:
            - Anypoint Platform Organization Name to work on
        required: true
    organization_id:
        description:
            - Anypoint Platform Organization ID. Default value retrieved based on organization
        required: false
    environment:
        description:
            - Environment on the Business Group to work on
        required: false
        default: Sandbox
    region:
        description:
            - Regions available to create a destination
        required: false
        choices: [ 'us-east-1', 'us-west-2', 'ca-central-1', 'eu-west-1', 'eu-west-2' ]
        default: 'us-east-1'
    attributes:
        description:
            - represents the attributes of the destination
        suboptions:
            encrypted:
                description:
                    - indicates if the destination is encrypted or not
                required: false
                choices: [ true, false ]
                default: false
            type:
                description:
                    - indicates the destination type
                choices: [ 'queue', 'exchange' ]
                default: 'queue'
            fifo:
                description:
                    - indicates if the queue is fifo or not (not valid for destination types exchange)
                required: false
                choices: [ true, false ]
                default: false
            default_ttl:
                description:
                    - indicates if the default TTL in ms for the destination
                required: false
                default: 604800000
            default_lock_ttl:
                description:
                    - indicates if the default lock TTL in ms for the destination
                required: false
                default: 120000
            dead_letter_queue:
                description:
                    - the name of the dead letter queue (if any)
                required: false
            max_deliveries:
                description:
                    - maximum number of deliveries before sending to DLQ (if any)
                required: false
                default: 10
            exchange_queues:
                description:
                    - a list of queues to use for the exchange destination type
                required: false

author:
    - Gonzalo Camino (@gonzalo-camino)
'''

EXAMPLES = '''
# Example of creating an MQ queue
- name: create an MQ queue
  ap_mq_destination:
    name: 'MyQueue'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    environment: 'Sandbox'
    attributes:
        type: 'queue'

# Example of deleting an MQ queue
- name: delete an exchange application
  ap_mq_destination:
    name: 'My App'
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    environment: 'Sandbox'

# Example of creating an MQ exchange
- name: create an MQ queue
  ap_mq_destination:
    name: 'myExchange'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    environment: 'Sandbox'
    attributes:
        type: 'exchange'
        exchange_queues:
            - queue1
            - queue2

# Example of deleting an MQ exchange
- name: delete an exchange application
  ap_mq_destination:
    name: 'myExchange'
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    environment: 'Sandbox'
'''

RETURN = '''
id:
    description: Destination id
    type: str
    returned: success
msg:
    description: Anypoint CLI command output
    type: str
    returned: always
'''

import json
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url


def get_mq_url(module):
    return 'https://' + module.params['host'] + '/mq/admin/api/v1/organizations/' + module.params['organization_id']


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


def get_org_id(module):
    org_id = None
    my_url = 'https://' + module.params['host'] + '/accounts/api/profile'
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}
    output = json.load(execute_http_call(module, my_url, 'GET', headers, None))
    for item in output['memberOfOrganizations']:
        if (item['name'] == module.params['organization']):
            org_id = item['id']
            break
    if (org_id is None):
        module.fail_json(msg='Business Group {' + module.params['organization'] + '} not found')

    return org_id


def get_environment_id(module):
    env_id = None
    my_url = 'https://' + module.params['host'] + '/accounts/api/organizations/' + module.params['organization_id'] + '/environments'
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}
    output = json.load(execute_http_call(module, my_url, 'GET', headers, None))

    for item in output['data']:
        if (item['name'] == module.params['environment']):
            env_id = item['id']
            break
    if (env_id is None):
        module.fail_json(msg='Environment {' + module.params['environment'] + '} not found onBusiness Group {' + module.params['organization'] + '}')

    return env_id


def get_mq_env_url(module, env_id):
    return get_mq_url(module) + '/environments/' + env_id + '/regions/' + module.params['region']


def get_existing_destinations(module, env_id):
    my_url = get_mq_env_url(module, env_id) + '/destinations?inclusion=MINIMAL'
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}

    return execute_http_call(module, my_url, 'GET', headers, None)


def get_context(module):
    return_value = dict(
        do_nothing=False,
        env_id=None,
        destination_id=None
    )
    app_exists = False
    url = None
    description = None

    return_value['env_id'] = get_environment_id(module)
    dest_list = json.load(get_existing_destinations(module, return_value['env_id']))

    for item in dest_list:
        if (module.params['attributes']['type'] == 'queue'):
            if ((item['type'] == 'queue') and (item['queueId'] == module.params['name'])):
                return_value['destination_id'] = item['queueId']
                break
        elif (module.params['attributes']['type'] == 'exchange'):
            if ((item['type'] == 'exchange') and (item['exchangeId'] == module.params['name'])):
                return_value['destination_id'] = item['exchangeId']
                break

    if (module.params['state'] == 'present'):
        return_value['do_nothing'] = (return_value['destination_id'] is not None)
    elif (module.params['state'] == 'absent'):
        return_value['do_nothing'] = (return_value['destination_id'] is None)

    return return_value


def set_exchange_id_on_queues(module, context):
    headers = {
        'Authorization': 'Bearer ' + module.params['bearer'],
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    partial_url = get_mq_env_url(module, context['env_id']) + '/bindings/exchanges/' + module.params['name'] + '/queues'
    for queue in module.params['attributes']['exchange_queues']:
        final_url = partial_url + '/' + queue
        output = execute_http_call(module, final_url, 'PUT', headers, None)

    return True


def create_mq_destination(module, context):
    return_value = dict(
        msg=None,
        destination_id=None
    )
    headers = {
        'Authorization': 'Bearer ' + module.params['bearer'],
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    my_url = get_mq_env_url(module, context['env_id']) + '/destinations'
    transactional_url = ('https://' + module.params['host'] + '/mq/organizations/' + module.params['organization_id'] +
                         '/environments/' + module.params['organization_id'] +
                         '/destinations/' + module.params['region'] +
                         '/list')

    if (module.params['attributes']['type'] == 'queue'):
        my_url += '/queues/' + module.params['name']
        payload = {
            'type': 'queue',
            'encrypted': module.params['attributes']['encrypted'],
            'defaultTtl': module.params['attributes']['default_ttl'],
            'defaultLockTtl': module.params['attributes']['default_lock_ttl']
        }
        if (module.params['attributes']['dead_letter_queue'] is not None):
            payload['deadLetterQueueId'] = module.params['attributes']['dead_letter_queue']
            payload['maxDeliveries'] = module.params['attributes']['max_deliveries']
        transactional_url += '/queues/' + module.params['name']
        # start transaction for queue creation, just ignore response
        output = execute_http_call(module, transactional_url, 'GET', headers, None)
    elif (module.params['attributes']['type'] == 'exchange'):
        my_url += '/exchanges/' + module.params['name']
        payload = {
            'type': 'exchange',
            'encrypted': module.params['attributes']['encrypted'],
            'exchangeId': module.params['name']
        }

    output = json.load(execute_http_call(module, my_url, 'PUT', headers, json.dumps(payload)))

    if (module.params['attributes']['type'] == 'queue'):
        return_value['destination_id'] = output['queueId']
    elif (module.params['attributes']['type'] == 'exchange'):
        return_value['destination_id'] = output['exchangeId']
        # set exchangeId on specified queues
        if (len(module.params['attributes']['exchange_queues']) > 0):
            output = set_exchange_id_on_queues(module, context)

    return_value['msg'] = 'MQ ' + module.params['attributes']['type'] + ' "' + module.params['name'] + '" created.'

    return return_value


def delete_mq_destination(module, context):
    return_value = dict(
        msg=None,
        destination_id=None
    )
    my_url = get_mq_env_url(module, context['env_id']) + '/destinations'
    if (module.params['attributes']['type'] == 'queue'):
        my_url += '/queues/' + module.params['name']
    elif (module.params['attributes']['type'] == 'exchange'):
        my_url += '/exchanges/' + module.params['name']

    headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }

    execute_http_call(module, my_url, 'DELETE', headers, None)
    return_value['msg'] = 'MQ Destination "' + module.params['name'] + '" deleted.'

    return return_value


def run_module():
    attributes_spec = dict(
        encrypted=dict(type='bool', required=False, default=False),
        type=dict(type='str', required=False, default='queue', choices=['queue', 'exchange']),
        fifo=dict(type='bool', required=False, default=False),
        default_ttl=dict(type='int', required=False, default=604800000),
        default_lock_ttl=dict(type='int', required=False, default=120000),
        dead_letter_queue=dict(type='str', required=False),
        max_deliveries=dict(type='int', required=False, default=10),
        exchange_queues=dict(type='list', required=False)
    )
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "absent"]),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization=dict(type='str', required=True),
        organization_id=dict(type='str', required=False),
        environment=dict(type='str', required=False, default='Sandbox'),
        region=dict(type='str', required=False, default='us-east-1', choices=['us-east-1', 'us-west-2', 'ca-central-1', 'eu-west-1', 'eu-west-2']),
        attributes=dict(type='dict', options=attributes_spec)
    )

    result = dict(
        changed=False,
        msg='No action taken',
        id=None
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Main Module Logic

    # exit if the execution is in check_mode
    if module.check_mode:
        module.exit_json(**result)

    # exit if I need to do nothing, so check if environment exists
    if (module.params['organization_id'] is None):
        module.params['organization_id'] = get_org_id(module)

    context = get_context(module)

    result['id'] = context['destination_id']

    if (context['do_nothing'] is True):
        module.exit_json(**result)

    # check arguments

    # finally do some stuff
    if (module.params['state'] == 'present'):
        output = create_mq_destination(module, context)
    elif (module.params['state'] == 'absent'):
        output = delete_mq_destination(module, context)

    result['changed'] = True
    result['id'] = output['destination_id']
    result['msg'] = output['msg']

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
