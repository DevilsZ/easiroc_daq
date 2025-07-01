================================================
===== Python Easiroc controller base on ========
=====  Ruby tool written by Naruhiro Chikuma ===
=====   2024-11-25 =============================
================================================

=== Controller for EASIROC firmware (ver. 2016-05-23).

=== To do, prepare conda create json 
$ conda create -n easiroc python=3.10

=== To run this program.
$ python Controller.py
(IP address may follow if it is changed from 192.168.10.16)
Outputs are put under the directory "data".

=== EASIROC/FPGA parameters are controlled by YAML cards.
- RegisterValue.yml
Any parameters of EASIROC slow control could be overwrite those in
DefaultRegisterValue. 
- InputDAC.yml
- PedestalSuppression.yml
- Calibration.yml

= Do not change the following cards.
- DefaultRegisterValue.yml
- RegisterAttribute.yml
- RegisterValueAlias.yml