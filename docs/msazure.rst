Azure Blob Storage
==================

Overview
--------

Memory acquisition is often performed in scenarios requiring careful separation between the
systems handling the captured memory data and the user's other computing environments. To save
the acquired memory, Margaritashotgun only needs the ability to write a new blob into a specific
storage container and does not require full access to login credentials. Using a
`SAS token`_ allows us to follow the principle of least privilege.

This procedure below uses `PowerShell <Azure PowerShell_>`_ on `Azure Cloud Shell`_
to generate the SAS token in the form of a URI.

It's also possible to run these commands locally in PowerShell, and corresponding commands are
available in `Azure CLI`_. The web portal and `Storage Explorer <Azure Storage Explorer_>`_
can also generate SAS URIs. But the method described here is simpler because Cloud Shell
provides a consistent, up-to-date installation and automatically handles user authentication.

* `SAS token`_
* `Azure PowerShell`_
* `Azure Cloud Shell`_
* `Azure CLI`_
* `Azure Storage Explorer`_
* `Azure web portal`_

.. _SAS token: https://docs.microsoft.com/en-us/azure/storage/common/storage-dotnet-shared-access-signature-part-1?toc=%2fazure%2fstorage%2fblobs%2ftoc.json
.. _Azure Cloud Shell: https://docs.microsoft.com/en-us/azure/cloud-shell/overview
.. _Azure PowerShell: https://docs.microsoft.com/en-us/powershell/azure/overview
.. _Azure CLI: https://docs.microsoft.com/en-us/cli/azure/
.. _Azure Storage Explorer: https://azure.microsoft.com/en-us/features/storage-explorer/
.. _Azure web portal: https://azure.microsoft.com/en-us/features/azure-portal/

Procedure
---------

1. Open Azure PowerShell
~~~~~~~~~~~~~~~~~~~~~~~~

From your preferred work environment, open a PowerShell terminal from
`Azure web portal`_ or directly at `shell.azure.com <https://shell.azure.com/>`_.

If you work with multiple subscriptions, ensure the correct one is selected.

.. code-block:: PowerShell

  (Get-AzContext).Subscription | Format-List

  Get-AzSubscription -SubscriptionName 'the subscription to use' | Set-AzContext

* `Manage multiple Azure subscriptions`_
* `Get-AzContext`_
* `Get-AzSubscription`_
* `Set-AzContext`_

.. _Manage multiple Azure subscriptions: https://docs.microsoft.com/en-us/powershell/azure/azurerm/manage-subscriptions-azureps
.. _Get-AzContext: https://docs.microsoft.com/en-us/powershell/module/az.accounts/get-azcontext
.. _Get-AzSubscription: https://docs.microsoft.com/en-us/powershell/module/az.accounts/get-azsubscription
.. _Set-AzContext: https://docs.microsoft.com/en-us/powershell/module/az.accounts/set-azcontext

2. Select the blob storage account
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

(Optional) Create a new storage account
:::::::::::::::::::::::::::::::::::::::

Decide the location in which the storage account will be created. A list of
location identifiers can be obtained with:

.. code-block:: PowerShell

  (Get-AzLocation).Location

Select (or create) a `resource group <Resource groups_>`__ into which the
new storage account will be placed. Note that a resource group is specific to
a location.

Choose the `SKU Type <SKU Types_>`_ and `storage tier <Storage tier_>`_.
These choices determine performance and redunancy of replication.

For more info, consult with whoever manages the Azure subscription and
the documentation linked below.

With these values known, create the new storage account.

.. code-block:: PowerShell

  New-AzStorageAccount -Name examplestorageaccount `
  -ResourceGroupName example-resource-group `
  -Kind BlobStorage `
  -EnableHttpsTrafficOnly $true `
  -SkuName [...] `
  -Location [...] `
  -AccessTier [...]

- A storage account name can contain only digits and lower-case letters.
- Using a storage account in the same geographic region as the target systems
  may reduce data transfer.

* `Quickstart\: Create a storage account`_
* `Manage storage accounts`_
* `Resource groups`_
* `Azure Storage`_
* `Storage redundancy`_
* `Storage tier`_
* `SKU Types`_
* `New-AzStorageAccount`_

.. _Quickstart\: Create a storage account: https://docs.microsoft.com/en-us/azure/storage/common/storage-quickstart-create-account?tabs=azure-powershell
.. _Manage storage accounts: https://docs.microsoft.com/en-us/azure/storage/common/storage-azure-cli#manage-storage-accounts
.. _Resource groups: https://docs.microsoft.com/en-us/azure/azure-resource-manager/resource-group-overview#resource-groups
.. _Azure Storage: https://docs.microsoft.com/en-us/azure/storage/
.. _Storage redundancy: https://docs.microsoft.com/en-us/azure/storage/common/storage-redundancy
.. _Storage tier: https://docs.microsoft.com/en-us/azure/storage/blobs/storage-blob-storage-tiers
.. _SKU Types: https://docs.microsoft.com/en-us/rest/api/storagerp/srp_sku_types
.. _New-AzStorageAccount: https://docs.microsoft.com/en-us/powershell/module/az.storage/new-azstorageaccount

Set the storage account as 'current'
::::::::::::::::::::::::::::::::::::

Azure PowerShell will keep track of the current storage account so you won't
need to specify it again for every command.

.. code-block:: PowerShell

  Set-AzCurrentStorageAccount -ResourceGroupName example-resource-group -Name examplestorageaccount

* `Set-AzCurrentStorageAccount`_

.. _Set-AzCurrentStorageAccount: https://docs.microsoft.com/en-us/powershell/module/az.storage/Set-AzCurrentStorageAccount

3. (Optional) Create a new storage container for the output
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: PowerShell

  New-AzStorageContainer -Name container-name

- A container name can't contain underscores, but it can have hyphens/minuses.
- Other name restrictions apply.

* `New-AzStorageContainer`_

.. _New-AzStorageContainer: https://docs.microsoft.com/en-us/powershell/module/az.storage/new-azstoragecontainer

4. Generate a time-limited SAS token having only the needed privileges
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It will be an URL identifying a specific container followed by a query string representing the SAS token.
This combined format is known as a 'SAS URI'.

.. code-block:: PowerShell

  New-AzStorageContainerSASToken -FullUri -Permission w -Name container-name

The output should look something like:

  https://examplestorageaccount.blob.core.windows.net/container-name?sv=2019-01-01&sr=c&sig=dGhpcyBpcyBqdXN0IGFuIGV4YW1wbGUK&se=2019-03-01T04%3A15%3A21Z&sp=w

- The default time of validity expiration is one hour. You may need to specify the ``-ExpiryTime`` (in UTC) if the capture
  process could take longer than that.

* `New-AzStorageContainerSASToken`_

.. _New-AzStorageContainerSASToken: https://docs.microsoft.com/en-us/powershell/module/az.storage/new-azstoragecontainersastoken

5. Install prerequisites
~~~~~~~~~~~~~~~~~~~~~~~~~

Ensure the blob storage component of the `Azure Python API <Azure Storage SDK for Python_>`_ is available
on the host from which you will run `margaritashotgun`.

.. code-block:: bash

  python -m pip install azure-storage-blob

* `Azure Storage SDK for Python`_

.. _Azure Storage SDK for Python: https://azure-storage.readthedocs.io/ref/azure.storage.blob.blockblobservice.html

6. Run `margaritashotgun`
~~~~~~~~~~~~~~~~~~~~~~~~~

Run `margaritashotgun` as usual, using the ``--azure-sas-uri`` command line argument
to supply the SAS URI generated in step 4 above.

.. code-block:: bash

   margaritashotgun --server 172.16.20.10 --username root --key root_access.pem --module lime-3.13.0-74-generic.ko --azure-sas-uri 'https://...'

* You will need to enclose the SAS URI in single quotes.

