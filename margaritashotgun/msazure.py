# vim: set sw=4 ts=4 et ai ff=unix:

from progressbar import ProgressBar
import logging
import socket
from margaritashotgun.exceptions import *
import sys
import traceback

logger = logging.getLogger(__name__)

def validate_azure_config(config):
    """
    Returns True if Azure blob output is in use.
    """

    azblob_allowed_keys = [
            "sas_uri"
            ]

    # optional configuration
    azure_blob_in_use = False
    try:
        for key in config['azure_blob'].keys():
            if config['azure_blob'][key] is not None:
                azure_blob_in_use = True
            if key not in azblob_allowed_keys:
                raise InvalidConfigurationError(key, config['azure_blob'][key])
    except KeyError:
        pass

    azure_blob_in_use

def capture_to_azblob(azure_blob_config, filename, tunnel_addr, tunnel_port, memory):

    # Verify that the Azure blob storage API package is available.
    try:
        from azure.storage.blob import BlockBlobService
    except ImportError as ex:
        logger.error("Ensure the Azure blob storage API is available, "
                     "e.g. 'pip install azure-storage-blob'.")
        raise

    if not filename:
        raise MemoryCaptureAttributeMissingError('filename')

    # Convert the supplied parameters into what we will need for the blob API
    interpret_blob_config(azure_blob_config)

    blob_name = filename

    memory_to_azure_blob(memory, blob_name, azure_blob_config, tunnel_addr, tunnel_port)

def set_or_compare(d, k, v):
    """
    Sets the value v at key k in dict d.
    If it already has a different value, raise.
    """
    v_current = d.get(k)
    if v_current is not None and v_current != v:
        raise InvalidConfigurationError(k, "Contradictory values for {}: {} and {}".format(k, v_current, v))
    d[k] = v

def interpret_blob_config(blob_config):
    """
    Modifies the blob_config in-place to convert the supplied configuration into
    the parameters needed for the Azure blob storage API.
    A supplied SAS URI is split into parts.
    Input keys may include:

    * sas_uri - SAS URI

    Output keys may include:

    * account_name - name of storage account
    * container_name
    * endpoint_suffix, e.g., 'core.windows.net'
    * sas_token - authorization query string, starting with '?'
    """

    sas_uri = blob_config.get('sas_uri')
    if not sas_uri:
        raise InvalidConfigurationError('sas_uri', "Expecting sas_uri")

    if sys.version_info[0] < 3:
        from urlparse import urlparse
    else:
        from urllib.parse import urlparse

    ur = urlparse(sas_uri)
    logger.debug("sas_uri scheme: '{}', netloc: '{}', "
                 "path: '{}', params: len={}, query: len={}, "
                 "fragment: '{}', username: '{}', password: len={}, "
                 "hostname: '{}', port: {}".format(
                 ur.scheme, ur.netloc, ur.path, len(ur.params or ''), len(ur.query or ''),
                 ur.fragment, ur.username, len(ur.password or ''), ur.hostname, ur.port))

    if ur.scheme != 'https':
        raise InvalidConfigurationError('sas_uri', "SAS URI scheme '{}' should be 'https'.".format(ur.scheme))

    # Remove any leading or trailing '/' from the path to obtain the container name
    container = ur.path
    while len(container) > 0:
        if container.endswith('/'):
            container = container[:-1]
        elif container.startswith('/'):
            container = container[1:]
        else:
            break
    set_or_compare(blob_config, 'container_name', container)

    if ur.username:
        raise InvalidConfigurationError('sas_uri', "SAS URI username '{}' not supported.".format(ur.username))

    if ur.password:
        raise InvalidConfigurationError('sas_uri', "SAS URI password not supported.", ur.password)

    if not (ur.port is None or ur.port == 443):
        raise InvalidConfigurationError('sas_uri', "SAS URI port '{}' not supported.".format(ur.port))

    # storage_account.service.endpoint_suffix, e.g., 'example.blob.core.windows.net'
    if not ur.hostname:
        raise InvalidConfigurationError('sas_uri', "SAS URI hostname expected.")
    account_name, service, endpoint_suffix = ur.hostname.split('.', 2)
    if service != 'blob':
        raise InvalidConfigurationError('sas_uri', "SAS URI service '{}' should be 'blob'.".format(service))
    set_or_compare(blob_config, 'account_name', account_name)

    if endpoint_suffix.find('.') < 0:
        raise InvalidConfigurationError('sas_uri', "SAS URI endpoint suffix '{}' should look like a DNS domain name.".format(endpoint_suffix))
    set_or_compare(blob_config, 'endpoint_suffix', endpoint_suffix)

    if not ur.query:
        raise InvalidConfigurationError('sas_uri', "SAS URI should have a SAS token query string")

    sas_token = '?' + ur.query
    set_or_compare(blob_config, 'sas_token', sas_token)

def memory_to_azure_blob(memory, blob_name, azure_blob_config, tunnel_addr, tunnel_port):
    """
    Writes memory dump to azure blob storage.

    Compare to:
        memory.Memory.to_file(),
        memory.Memory.to_s3()

    :type memory: str
    :param memory: instance of memory.Memory() corresponding to 'self' in to_file()
    :type blob_name: str
    :param blob_name: name of destination blob derived from filename
    :type azure_blob_config: dict
    :param azure_blob_config: configuration parameters for Azure blob storage
    :type tunnel_addr: str
    :param tunnel_port: ssh tunnel hostname or ip
    :type tunnel_port: int
    :param tunnel_port: ssh tunnel port
    """

    from azure.storage.blob import BlockBlobService

    if memory.progressbar:
        memory.bar = ProgressBar(maxval=memory.max_size, widgets=memory.widgets)
        memory.bar.start()

    memory.transfered = 0
    memory.update_progress()

    blobservice_args = { }

    account_name = azure_blob_config.get('account_name')
    if account_name:
        blobservice_args['account_name'] = account_name
        logger.debug('BlockBlobService account_name: {0}'.format(account_name))

    # Not supporting account_key in favor of SAS token authorization.

    sas_token = azure_blob_config.get('sas_token')
    if sas_token:
        blobservice_args['sas_token'] = sas_token
        logger.debug('BlockBlobService sas_token: [redacted]')

    endpoint_suffix = azure_blob_config.get('endpoint_suffix')
    if endpoint_suffix:
        blobservice_args['endpoint_suffix'] = endpoint_suffix
        logger.debug('BlockBlobService endpoint_suffix: {0}'.format(endpoint_suffix))

    container_name = azure_blob_config.get('container_name')

    block_blob_svc = BlockBlobService(**blobservice_args)

    memory.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    memory.sock.connect((tunnel_addr, tunnel_port))
    memory.sock.settimeout(memory.sock_timeout)

    def prog_cb(memory, current, _total):
        memory.transfered = current
        memory.update_progress()

    logger.info('{0}: capturing to Azure blob: [{1}]/{2}/{3}'.format(
            memory.remote_addr, account_name, container_name, blob_name))

    try:
        stream = memory.sock.makefile(mode='rb')

        resource_props = block_blob_svc.create_blob_from_stream(
            container_name,
            blob_name,
            stream,
            progress_callback = lambda current, total: prog_cb(memory, current, total),
            max_connections = 1,
            if_none_match = '*') # don't overwrite any existing blob
    except Exception as e: # Get traceback
        logger.error('azure.storage.blob.BlockBlobService.create_blob_from_stream(): ' +
            traceback.format_exc())
        raise
    finally:
        if memory.sock:
            memory.sock.close()

    memory.cleanup()

    logger.info('{0}: capture complete: Azure blob: [{1}]/{2}/{3}'.format(
            memory.remote_addr, account_name, container_name, blob_name))

    return True
