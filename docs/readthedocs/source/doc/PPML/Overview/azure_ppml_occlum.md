# BigDL PPML Azure Occlum Example

## Overview

This documentation demonstrates how to run standard Apache Spark applications with BigDL PPML and Occlum on Azure Intel SGX enabled Confidential Virtual machines ([DCsv3](https://docs.microsoft.com/en-us/azure/virtual-machines/dcv3-series) or [Azure Kubernetes Service (AKS)](https://azure.microsoft.com/en-us/services/kubernetes-service/)). These Azure Virtual Machines include the Intel SGX extensions.

Key points:

* Azure Cloud Services:  
    * [Azure Data Lake Storage](https://azure.microsoft.com/en-us/services/storage/data-lake-storage/): a secure cloud storage platform that provides scalable, cost-effective storage for big data analytics. 
    * [Key Vault](https://azure.microsoft.com/en-us/services/key-vault/): Safeguard cryptographic keys and other secrets used by cloud apps and services. Although, this solution works for all Azure Key Valut types, it is recommended to use [Azure Key Vault Managed HSM](https://learn.microsoft.com/en-us/azure/key-vault/managed-hsm/overview) (FIPS 140-2 Level 3) for better safety.
    * [Attestation Service](https://azure.microsoft.com/en-us/services/azure-attestation/): A unified solution for remotely verifying the trustworthiness of a platform and integrity of the binaries running inside it.

    ![Distributed Spark in SGX on Azure](../images/spark_sgx_azure.png)

* Occlum: Occlum is a memory-safe, multi-process library OS (LibOS) for Intel SGX. As a LibOS, it enables legacy applications to run on Intel® SGX with little to no modifications of source code, thus protecting the confidentiality and integrity of user workloads transparently.

    ![Microsoft Azure Attestation on Azure](../images/occlum_maa.png)

* For Azure attestation details in Occlum init process please refer to [`maa_init`](https://github.com/occlum/occlum/tree/master/demos/remote_attestation/azure_attestation/maa_init).

## Prerequisites

* Set up Azure VM on Azure
    * Create a [DCSv3](https://docs.microsoft.com/en-us/azure/virtual-machines/dcv3-series) VM for [single node spark example](#single-node-spark-examples-on-azure).
    * Prepare image of Spark (Required for distributed Spark examples only)
      * Login to the created VM, then download [Spark 3.1.2](https://archive.apache.org/dist/spark/spark-3.1.2/spark-3.1.2-bin-hadoop3.2.tgz) and extract Spark binary. Install OpenJDK-8, and `export SPARK_HOME=${Spark_Binary_dir}`.
    * Go to Azure Marketplace, search "BigDL PPML" and find `BigDL PPML: Secure Big Data AI on Intel SGX (experimental and reference only, Occlum Edition)` product. Click "Create" button which will lead you to `Subscribe` page.
      On `Subscribe` page, input your subscription, your Azure container registry, your resource group and your location. Then click `Subscribe` to subscribe BigDL PPML Occlum to your container registry.
    * On the created VM, login to your Azure container registry, then pull BigDL PPML Occlum image using this command:
    ```bash
    docker pull myContainerRegistry.azurecr.io/intel_corporation/bigdl-ppml-azure-occlum:latest
    ```
* Set up [Azure Kubernetes Service (AKS)](https://azure.microsoft.com/en-us/services/kubernetes-service/) for [distributed Spark examples](#distributed-spark-example-on-aks).
  * Follow the [guide](https://learn.microsoft.com/en-us/azure/confidential-computing/confidential-enclave-nodes-aks-get-started) to deploy an AKS with confidential computing Intel SGX nodes.
  * Install Azure CLI on the created VM or your local machine according to [Azure CLI guide](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli).
  * Login to AKS with such command:
  ```bash
  az aks get-credentials --resource-group  myResourceGroup --name myAKSCluster
  ```
  * Create image pull secret from your Azure container registry
      * If you already logged in to your Azure container registry, find your docker config json file (i.e. ~/.docker/config.json), and create secret for your registry credential like below:
      ```bash
      kubectl create secret generic regcred \
      --from-file=.dockerconfigjson=<path/to/.docker/config.json> \
      --type=kubernetes.io/dockerconfigjson
      ```
      * If you haven't logged in to your Azure container registry, you can create secret for your registry credential using your username and password:
      ```bash
      kubectl create secret docker-registry regcred --docker-server=myContainerRegistry.azurecr.io --docker-username=<your-name> --docker-password=<your-pword> --docker-email=<your-email>
      ```
  * Create the RBAC to AKS
    ```bash
    kubectl create serviceaccount spark
    kubectl create clusterrolebinding spark-role --clusterrole=edit --serviceaccount=default:spark --namespace=default
    ```
  * Add image pull secret to service account
    ```bash
    kubectl patch serviceaccount spark -p '{"imagePullSecrets": [{"name": "regcred"}]}'
    ```
  
## Single Node Spark Examples on Azure
### SparkPi example

On the VM, Run the SparkPi example with `run_spark_on_occlum_glibc.sh`.

```bash
docker run --rm -it \
    --name=azure-ppml-example-with-occlum \
    --device=/dev/sgx/enclave \
    --device=/dev/sgx/provision \
    myContainerRegistry.azurecr.io/intel_corporation/bigdl-ppml-azure-occlum:latest bash 
cd /opt
bash run_spark_on_occlum_glibc.sh pi
```

### Nytaxi example with Azure NYTaxi

On the VM, run the Nytaxi example with `run_azure_nytaxi.sh`.

```bash
docker run --rm -it \
    --name=azure-ppml-example-with-occlum \
    --device=/dev/sgx/enclave \
    --device=/dev/sgx/provision \
    myContainerRegistry.azurecr.io/intel_corporation/bigdl-ppml-azure-occlum:latest bash 
bash run_azure_nytaxi.sh
```

You should get Nytaxi dataframe count and aggregation duration when succeed.

## Distributed Spark Examples on AKS
Clone the repository to the VM:
```bash
git clone https://github.com/intel-analytics/BigDL-PPML-Azure-Occlum-Example.git
```
### SparkPi on AKS

In `run_spark_pi.sh` script, update `IMAGE` variable to `myContainerRegistry.azurecr.io/intel_corporation/bigdl-ppml-azure-occlum:latest`, and configure your AKS address. In addition, configure environment variables in `driver.yaml` and `executor.yaml` too. Then you can submit SparkPi task with `run_spark_pi.sh`.

```bash
bash run_spark_pi.sh
```

### Nytaxi on AKS

In `run_nytaxi_k8s.sh` script, update `IMAGE` variable to `myContainerRegistry.azurecr.io/intel_corporation/bigdl-ppml-azure-occlum:latest`, and configure your AKS address. In addition, configure environment variables in `driver.yaml` and `executor.yaml` too. Then you can submit Nytaxi query task with `run_nytaxi_k8s.sh`.
```bash
bash run_nytaxi_k8s.sh
```
### Run TPC-H example
TPC-H queries are implemented using Spark DataFrames API running with BigDL PPML.

#### Generating tables

Go to [TPC Download](https://www.tpc.org/tpc_documents_current_versions/current_specifications5.asp) site, choose `TPC-H` source code, then download the TPC-H toolkits.
After you download the TPC-h tools zip and uncompressed the zip file. Go to `dbgen` directory and create a makefile based on `makefile.suite`, and run `make`.

This should generate an executable called `dbgen`.

```
./dbgen -h
```

`dbgen` gives you various options for generating the tables. The simplest case is running:

```
./dbgen
```
which generates tables with extension `.tbl` with scale 1 (default) for a total of rougly 1GB size across all tables. For different size tables you can use the `-s` option:
```
./dbgen -s 10
```
will generate roughly 10GB of input data.

#### Generate primary key and data key
Generate primary key and data key, then save to file system.

The example code for generating the primary key and data key is like below:
```
BIGDL_VERSION=2.1.0
java -cp '/opt/bigdl-$BIGDL_VERSION/jars/*:/opt/spark/conf/:/opt/spark/jars/* \
   -Xmx10g \
   com.intel.analytics.bigdl.ppml.examples.GenerateKeys \
   --kmsType AzureKeyManagementService \
   --vaultName xxx \
   --primaryKeyPath xxx/keys/primaryKey \
   --dataKeyPath xxx/keys/dataKey
```
After generate keys on local fs, you may upload keys to Azure Data Lake store for running TPC-H with cluster mode.

The example script is like below:

```bash
az storage fs directory upload -f myFS --account-name myDataLakeAccount -s xxx/keys -d myDirectory/keys --recursive
```

#### Encrypt Data
Encrypt data with specified BigDL `AzureKeyManagementService`

The example code of encrypting data is like below:
```
BIGDL_VERSION=2.1.0
java -cp '/opt/bigdl-$BIGDL_VERSION/jars/*:/opt/spark-3.1.2/conf/:/opt/spark/jars/* \
   -Xmx10g \
   com.intel.analytics.bigdl.ppml.examples.tpch.EncryptFiles \
   --kmsType AzureKeyManagementService \
   --vaultName xxx \
   --primaryKeyPath xxx/keys/primaryKey \
   --dataKeyPath xxx/keys/dataKey \
   --inputPath xxx/dbgen \
   --outputPath xxx/dbgen-encrypted
```

After encryption, you may upload encrypted data to Azure Data Lake store.

The example script is like below:

```bash
az storage fs directory upload -f myFS --account-name myDataLakeAccount -s xxx/dbgen-encrypted -d myDirectory --recursive
```

#### Running
Configure variable in run_tpch.sh to set Spark home, KeyVault, Azure Storage information, etc. 
Make sure you set the INPUT_DIR and OUTPUT_DIR in `TpchQuery` class before compiling to point to the
location of the input data and where the output should be saved.

The example script to run a query is like:

```
BIGDL_VERSION=2.1.0
export SPARK_HOME=
SPARK_EXTRA_JAR_PATH=/bin/jars/bigdl-ppml-spark_3.1.2-${BIGDL_VERSION}.jar
SPARK_JOB_MAIN_CLASS=com.intel.analytics.bigdl.ppml.examples.tpch.TpchQuery
IMAGE=myContainerRegistry.azurecr.io/intel_corporation/bigdl-ppml-azure-occlum:latest

KEYVAULT_NAME=
DATA_LAKE_NAME=
DATA_LAKE_ACCESS_KEY=
FS_PATH=abfs://xxx@xxx.dfs.core.windows.net
INPUT_DIR=$FS_PATH/dbgen/dbgen-encrypted-1g
ENCRYPT_KEYS_PATH=$FS_PATH/keys
OUTPUT_DIR=$FS_PATH/dbgen/out-dbgen-1g

export kubernetes_master_url=

${SPARK_HOME}/bin/spark-submit \
    --master k8s://https://${kubernetes_master_url} \
    --deploy-mode cluster \
    --name spark-tpch \
    --conf spark.rpc.netty.dispatcher.numThreads=32 \
    --conf spark.kubernetes.container.image=${IMAGE} \
    --conf spark.kubernetes.authenticate.driver.serviceAccountName=spark \
    --conf spark.kubernetes.executor.deleteOnTermination=false \
    --conf spark.kubernetes.driver.podTemplateFile=./driver.yaml \
    --conf spark.kubernetes.executor.podTemplateFile=./executor.yaml \
    --conf spark.kubernetes.file.upload.path=file:///tmp \
    --conf spark.kubernetes.sgx.log.level=error \
    --conf spark.kubernetes.driverEnv.DRIVER_MEMORY=2g \
    --conf spark.kubernetes.driverEnv.SGX_MEM_SIZE="25GB" \
    --conf spark.kubernetes.driverEnv.META_SPACE=1024M \
    --conf spark.kubernetes.driverEnv.SGX_HEAP="1GB" \
    --conf spark.kubernetes.driverEnv.SGX_KERNEL_HEAP="2GB" \
    --conf spark.kubernetes.driverEnv.SGX_THREAD="1024" \
    --conf spark.kubernetes.driverEnv.FS_TYPE="hostfs" \
    --conf spark.executorEnv.SGX_MEM_SIZE="16GB" \
    --conf spark.executorEnv.SGX_KERNEL_HEAP="2GB" \
    --conf spark.executorEnv.SGX_HEAP="1GB" \
    --conf spark.executorEnv.SGX_THREAD="1024" \
    --conf spark.executorEnv.SGX_EXECUTOR_JVM_MEM_SIZE="7G" \
    --conf spark.kubernetes.driverEnv.SGX_DRIVER_JVM_MEM_SIZE="1G" \
    --conf spark.executorEnv.FS_TYPE="hostfs" \
    --num-executors 1  \
    --executor-cores 4 \
    --executor-memory 3g \
    --driver-cores 4 \
    --conf spark.cores.max=4 \
    --conf spark.driver.defaultJavaOptions="-Dlog4j.configuration=/opt/spark/conf/log4j2.xml" \
    --conf spark.executor.defaultJavaOptions="-Dlog4j.configuration=/opt/spark/conf/log4j2.xml" \
    --conf spark.network.timeout=10000000 \
    --conf spark.executor.heartbeatInterval=10000000 \
    --conf spark.python.use.daemon=false \
    --conf spark.python.worker.reuse=false \
    --conf spark.sql.auto.repartition=true \
    --conf spark.default.parallelism=400 \
    --conf spark.sql.shuffle.partitions=400 \
    --conf spark.hadoop.fs.azure.account.auth.type.${DATA_LAKE_NAME}.dfs.core.windows.net=SharedKey \
    --conf spark.hadoop.fs.azure.account.key.${DATA_LAKE_NAME}.dfs.core.windows.net=${DATA_LAKE_ACCESS_KEY} \
    --conf spark.hadoop.fs.azure.enable.append.support=true \
    --conf spark.bigdl.kms.type=AzureKeyManagementService \
    --conf spark.bigdl.kms.azure.vault=$KEYVAULT_NAME \
    --conf spark.bigdl.kms.key.primary=$ENCRYPT_KEYS_PATH/primaryKey \
    --conf spark.bigdl.kms.key.data=$ENCRYPT_KEYS_PATH/dataKey \
    --class $SPARK_JOB_MAIN_CLASS \
    --verbose \
    local:$SPARK_EXTRA_JAR_PATH \
    $INPUT_DIR \
    $OUTPUT_DIR \
    AES/CBC/PKCS5Padding \
    plain_text [QUERY]
```

INPUT_DIR is the TPC-H's data dir.
OUTPUT_DIR is the dir to write the query result.
The optional parameter [QUERY] is the number of the query to run e.g 1, 2, ..., 22

## Known issues

1. If you meet the following error when running the docker image:

    ```bash
    aesm_service[10]: Failed to set logging callback for the quote provider library.
    aesm_service[10]: The server sock is 0x5624fe742330
    ```

    This may be associated with [SGX DCAP](https://github.com/intel/linux-sgx/issues/812). And it's expected error message if not all interfaces in quote provider library are valid, and will not cause a failure.

2. If you meet the following error when running MAA example:

    ```bash
    [get_platform_quote_cert_data ../qe_logic.cpp:352] p_sgx_get_quote_config returned NULL for p_pck_cert_config.
    thread 'main' panicked at 'IOCTRL IOCTL_GET_DCAP_QUOTE_SIZE failed', /opt/src/occlum/tools/toolchains/dcap_lib/src/occlum_dcap.rs:70:13
    note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
    [ERROR] occlum-pal: The init process exit with code: 101 (line 62, file src/pal_api.c)
    [ERROR] occlum-pal: Failed to run the init process: EINVAL (line 150, file src/pal_api.c)
    [ERROR] occlum-pal: Failed to do ECall: occlum_ecall_broadcast_interrupts with error code 0x2002: Invalid enclave identification. (line 26, file src/pal_interrupt_thread.c)
    /opt/occlum/build/bin/occlum: line 337:  3004 Segmentation fault      (core dumped) RUST_BACKTRACE=1 "$instance_dir/build/bin/occlum-run" "$@"
    ```

    This may be associated with [[RFC] IOCTRL IOCTL_GET_DCAP_QUOTE_SIZE failed](https://github.com/occlum/occlum/issues/899).

## Reference

1.	<https://github.com/intel-analytics/BigDL-PPML-Azure-Occlum-Example> 
2.	<https://www.intel.com/content/www/us/en/developer/tools/software-guard-extensions/overview.html> 
3.	<https://www.databricks.com/glossary/what-are-spark-applications>
4.	<https://github.com/occlum/occlum> 
5.	<https://github.com/intel-analytics/BigDL>
6.	<https://docs.microsoft.com/en-us/azure/open-datasets/dataset-taxi-yellow>
7.	<https://azure.microsoft.com/en-us/services/storage/data-lake-storage/>
8.	<https://azure.microsoft.com/en-us/services/key-vault/>
9.	<https://azure.microsoft.com/en-us/services/azure-attestation/>
10.	<https://github.com/Azure-Samples/confidential-container-samples/blob/main/confidential-big-data-spark/README.md>
11.	<https://bigdl.readthedocs.io/en/latest/doc/PPML/Overview/ppml.html> 
