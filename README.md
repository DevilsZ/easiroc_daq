# Python Easiroc controller
- base on the Ruby tool by N.Chikuma
- Written by Kentaro Kawade 2025-7-25
- based on firmware (ver. 2016-05-23??)

## Getting started
```console: Create environment
$ conda create -n easiroc python=3.10
$ conda activate easiroc
$ conda install pip
$ pip install pyyaml
$ pip install tqdm
```

## Excute program
```console: Open gui two modules controller
$ python gui.py
```

## Prepare yaml confuguration files
- EASIROC/FPGA parameters are controlled by YAML files
  - Separated for Parent/Child modules
    - RegisterValue.ymlAny 
      - parameters of EASIROC slow control could be overwrite
    - TriggerPLA.yml
  - Common yaml files needed to be optimized
    - InputDAC.yml
    - PedestalSuppression.yml
    - DefaultRegisterValue.yml
  - Common yaml files do not changed
    - Calibration.yml
    - DefaultRegisterValue.yml
    - RegisterAttribute.yml
    - RegisterValueAlias.yml
    