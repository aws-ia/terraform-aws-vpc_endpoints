#!/usr/bin/env python3

import json
import boto3


def get_endpoint_services(session=boto3):
    ec2 = session.client('ec2', region_name='us-east-1')
    service_details = ec2.describe_vpc_endpoint_services()['ServiceDetails']
    svc_map = {"Interface": {}, "Gateway": {}}
    for svc in service_details:
        if svc['Owner'] != "amazon":
            print(f"skipping non-amazon endpoint {svc['ServiceName']}")
            continue
        if svc['AcceptanceRequired']:
            print(f"skipping endpoint that requires acceptance {svc['ServiceName']}")
            continue
        if svc['ManagesVpcEndpoints']:
            print(f"skipping endpoint that manages vpc endpoints {svc['ServiceName']}")
            continue
        svc_type = svc["ServiceType"][0]["ServiceType"]
        svc_name = svc["ServiceName"]
        if svc_name.startswith("aws.sagemaker."):
            svc_name = f'sagemaker.{svc_name.split(".")[-1]}'
        elif svc_name.startswith("com.amazonaws."):
            if svc_name.split('.')[2] != 'us-east-1':
                svc_name = '.'.join(svc_name.split('.')[2:])
            else:
                svc_name = '.'.join(svc_name.split('.')[3:])
        else:
            print(f"skipping endpoint that has unexpected name format {svc['ServiceName']}")
            continue
        svc_name = svc_name.replace(".", "_")
        if len(svc['BaseEndpointDnsNames']) > 1:
            for i in range(len(svc['BaseEndpointDnsNames']) - 1):
                if svc['BaseEndpointDnsNames'][i].startswith(svc['ServiceId']):
                    svc['BaseEndpointDnsNames'].pop(i)
        if len(svc['BaseEndpointDnsNames']) > 1:
            print(f"skipping endpoint that has unexpected additional dns name {svc['ServiceName']} "
                  f"{svc['BaseEndpointDnsNames']}")
            continue
        private_dns_name = svc['PrivateDnsName'].replace("us-east-1", "<REGION>") if svc.get('PrivateDnsName') else None
        svc_map[svc_type][svc_name] = {
            'ServiceName': svc["ServiceName"].replace("us-east-1", "<REGION>"),
            # AZ's need more work, need to build a map of all supported az id's(not names) across all partitions
            # "AvailabilityZones": svc.get("AvailabilityZones"),
            'BaseEndpointDnsName': svc['BaseEndpointDnsNames'][0].replace("us-east-1", "<REGION>"),
            'VpcEndpointPolicySupported': svc['VpcEndpointPolicySupported'],
            'PrivateDnsName': private_dns_name
        }
    return svc_map


def generate_tf_json(endpoints):
    with open('./templates/locals.tf.json') as fp:
        tf_locals_template = json.load(fp)
    with open('./templates/main.tf.json') as fp:
        tf_resources_template = json.load(fp)
    with open('./templates/outputs.tf.json') as fp:
        tf_outputs_template = json.load(fp)
    with open('./templates/variables.tf.json') as fp:
        tf_variables_template = json.load(fp)
    tf_locals = tf_locals_template['locals']
    tf_endpoints = tf_resources_template['resource']['aws_vpc_endpoint']
    tf_outputs = tf_outputs_template['output']
    tf_variables = tf_variables_template['variable']
    for endpoint_type, eps in endpoints.items():
        for name, ep in eps.items():
            resource_name = f"{name}_{endpoint_type.lower()}"
            tf_endpoints[resource_name] = {
                "count": '${var.%s_enabled ? 1 : 0}' % resource_name,
                "service_name": regional_string(ep["ServiceName"]),
                "vpc_endpoint_type": endpoint_type,
                "tags": "${var.tags}",
                "auto_accept": True,
                "vpc_id": "${var.vpc_id}"
            }
            if endpoint_type == 'Gateway':
                tf_endpoints[resource_name]['route_table_ids'] = '${length(var.route_table_ids) > 0 ? var.route_table_ids : null}'
            elif endpoint_type == 'Interface':
                tf_endpoints[resource_name]['security_group_ids'] = '${var.security_group_ids}'
                tf_endpoints[resource_name]['subnet_ids'] = '${length(var.subnet_ids) > 0 ? var.subnet_ids : null}'
            if ep["VpcEndpointPolicySupported"]:
                tf_endpoints[resource_name]['policy'] = '${var.%s_policy}' % resource_name
                tf_variables[f"{resource_name}_policy"] = {
                    "type": "string",
                    "description": f"A policy to attach to the {name} {endpoint_type} endpoint that controls access to the service. This is a JSON formatted string. Defaults to full access.",
                    "default": None
                }
            tf_variables[f"{resource_name}_enabled"] = {
                "type": "bool",
                "description": f"Set to true to enable {name} {endpoint_type} endpoint.",
                "default": False
            }
    with open('./main.tf.json', "w") as fp:
        json.dump(tf_resources_template, fp)
    with open('./variables.tf.json', "w") as fp:
        json.dump(tf_variables_template, fp)


def regional_string(string):
    return '${replace("%s", "<REGION>", data.aws_region.current.name)}' % string


if __name__ == '__main__':
    endpoints = get_endpoint_services()
    generate_tf_json(endpoints)