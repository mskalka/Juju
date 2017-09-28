#!usr/bin/python3
"""Assess multimodel support."""

from jujupy import (
    get_basic_testing_parser,
    get_testing_client
    )


def assess_multimodel(client, args):
    """Assess handling of complex, multi-model environments

    Deploy charms in one model, then add another model and deploy
    charms there. Check that the dummy sink and dummy source charms
    in each model respond with the correct token

    :param client: Jujupy client object
    :param args: ArgumentParser object
    """
    model_one = client.get_current_model()
    deploy_testing_charms(client, model_one, 'model1')
    verify_token(client, model_one, 'model1')
    model_two = client.add_model(model_one + 'model_two')
    deploy_testing_charms(client, model_two, 'model2')
    verify_token(client, model_two, 'model2')


def deploy_testing_charms(client, model, token):
    client.deploy('dummy-sink', model=model)
    client.deploy('dummy-source', model=model)
    client.juju('add-relation', ['dummy-sink', 'dummy-source'],
                model=model)
    client.juju('config', ['dummy-sink', 'token={}'.format(token)],
                model=model)


def verify_token(client, model, token):
    returned = client.juju('config', ['dummy-sink', 'token'], model=model)
    if not returned == token:
        raise Exception(
            'Token mismatch in {}: Expected {}, got {}'.format(model, token,
                                                               returned))


def parse_args(argv=None):
    parser = get_basic_testing_parser()
    return parser.parse_args(argv)


def main():
    args = parse_args()
    with get_testing_client(args) as client:
        assess_multimodel(client, args)
