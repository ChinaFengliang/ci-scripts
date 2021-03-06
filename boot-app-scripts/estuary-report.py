#!/usr/bin/python
# <variable> = required
# Usage ./lava-report.py <option> [json]
# pip install matplotlib
# pip install numpy
# pip install reportlab
import os
import xmlrpclib
import yaml
import argparse
import time
import re
import shutil
import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import numpy as np
from lib import configuration
from lib import utils

from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer,Image,Table,TableStyle


# for test report
whole_summary_name = 'whole_summary.txt'
details_summary_name = 'details_summary.txt'
total_str = "Total number of test cases: "
fail_str = "Failed number of test cases: "
suc_str = "Success number of test cases: "

job_result_dict={}

device_map = {'d03': ['hip06-d03', 'hisi'],
              'd03ssh': ['d03ssh01','hisi'],
              'd05': ['d05_01', 'hisi'],
              'd05ssh': ['d05ssh01','hisi'],
              'ssh': ['ssh01', None],
              #'dummy_ssh': ['hip05-d02', 'hisi'],
              'x86': ['x86', None],
              'dummy-ssh': ['dummy-ssh', None],
              'kvm': ['x86-kvm', None]}


def parse_yaml(yaml):
    jobs = utils.load_yaml(yaml)
    url = utils.validate_input(jobs['username'], jobs['token'], jobs['server'])
    connection = utils.connect(url)
    duration = jobs['duration']
    # Remove unused data
    jobs.pop('duration')
    jobs.pop('username')
    jobs.pop('token')
    jobs.pop('server')
    return connection, jobs, duration


# add by wuyanjun
def get_board_type(directory, filename):
    strinfo = re.compile('.txt')
    json_name = strinfo.sub('.json', filename)
    test_info = utils.load_json(os.path.join(directory, json_name))
    if 'board' in test_info.keys():
        # for dummy-ssh board
        board_type = ''
        try:
            if re.search('ssh', test_info['board_instance']):
                board_type = test_info['board_instance'].split('_')[0]
            else:
                if ',' in test_info['board']:
                    board_verify = test_info['board'].split(',')[0]
                    for key in device_map.keys():
                        if device_map[key][0] == board_verify:
                            board_type = key
                            break
                        else:
                            board_type = ''
                else:
                    # for dummy_ssh_{board_type}
                    board_type = test_info['board'].split('_')[-1]
        except KeyError:
            if ',' in test_info['board']:
                try:
                    board_verify = test_info['board'].split(',')[0]
                except:
                    board_verify = test_info['board']
                    for key in device_map.keys():
                        if device_map[key][0] == board_verify:
                            board_type = key
                            break
                        else:
                            board_type = ''
            else:
                # for jobs which has not incomplete
                board_type = test_info['board'].split('_')[-1]
        return board_type
    return ''


def get_plans(directory, filename):
    m = re.findall('[A-Z]+_?[A-Z]*', filename)
    if m:
        root_dir = directory
        while '.git' not in os.listdir(root_dir):
            root_dir = os.path.join(root_dir, os.path.pardir)
        root_dir = os.path.abspath(root_dir)
        for item in m:
            for root, dirs, files in os.walk(os.path.join(root_dir, "boot-app-scripts", "templates")):
                for dir_item in dirs:
                    if dir_item == item:
                       return item
    return ''


def parser_and_get_result(contents, filename, directory, report_directory, connection):
    summary_post = '_summary.txt'
    if filename.endswith('.txt'):
        board_type = get_board_type(directory, filename)
        plan = get_plans(report_directory, filename)
        if board_type and plan:
            summary = board_type + '_' + plan + summary_post
        elif board_type:
            summary = board_type + summary_post
        elif plan:
            summary = plan + summary_post
        else:
            summary = 'summary.txt'
        with open(os.path.join(report_directory, summary), 'a') as sf:
            job_id = filename.split("_")[-1].split(".")[0]
            with open(os.path.join(directory, filename)) as fp:
                lines = fp.readlines()
            write_flag = 0
            # for job which has been run successfully
            with open(os.path.join(directory, filename)) as fp:
                contents = fp.read()
            if re.search("=+", contents) and re.search('Test.*?case.*?Result', contents):
                for i in range(0, len(lines)):
                    line = lines[i]
                    if write_flag == 1:
                        sf.write(line)
                        continue
                    if re.search("=+", line) and re.search("=+", lines[i+2]) and re.search('Test.*?case.*?Result', lines[i+3]):
                            write_flag = 1
                            sf.write("job_id is: %s\n" % job_id)
                            sf.write(line)
                    sf.write('\n')
            # for jobs which is Incomplete
            else:
                job_details = connection.scheduler.job_details(job_id)
                job_name = re.findall('testdef.*\/(.*?)\.yaml', job_details['original_definition'])
                sf.write("job_id is: %s\n" % job_id)
                sf.write("="*13 + "\n")
                sf.write(' '.join(job_name) + "\n")
                sf.write("="*13 + "\n")
                sf.write(' '.join(job_name) + "_test_cases\t\tFAIL\n\n")


# add by zhangbp0704
# parser the test result by lava v2
def generate_test_report(job_id, connection):
    testjob_results = connection.results.get_testjob_results_yaml(job_id)
    # print testsuite_results
    test = yaml.load(testjob_results)
    if job_id not in job_result_dict:
          job_result_dict[job_id] = test


def print_base_info_pie_chart(result_dict,description):
    suite_dict={}
    for suite in result_dict.keys():
        print suite
        for situation in result_dict[suite]:
            if situation not in suite_dict:
                suite_dict[situation]=result_dict[suite][situation]
            else:
                value=suite_dict[situation]
                value=value+result_dict[suite][situation]
                suite_dict[situation] = value
    situation_list = []
    result_list = []
    for key in suite_dict.keys():
        result_list.append(suite_dict[key])
        situation_list.append(key)
    plt.axes(aspect=1)
    plt.title(description)
    plt.pie(x=result_list, labels=situation_list,autopct='%3.1f %%',
        shadow=True, labeldistance=1.1, startangle=90, pctdistance=0.6)
    plt.savefig("baseinfo_pie.jpg")
    plt.close()


def print_scope_info_bar_chart(result_dict,description):
    scope_list=[]
    scope_list=result_dict.keys()

    pass_number_list = []
    for key in result_dict.keys():
        pass_number_list.append(result_dict[key])

    plt.legend()
    x_pos = np.arange(len(scope_list))
    plt.bar(x_pos, pass_number_list, 0.35,facecolor='blue', edgecolor='white',align='center',alpha=0.4)
    plt.xticks(x_pos,scope_list)
    plt.xlabel("Scope")
    plt.ylabel("Pass Number")
    plt.title(description)
    plt.savefig("baseinfo_bar.jpg")
    plt.close()


def create_test_report_pdf(job_result_dict):
#    print job_result_dict
    story=[]
    stylesheet=getSampleStyleSheet()
    normalStyle=stylesheet['Normal']
    curr_date=time.strftime("%Y-%m-%d", time.localtime())
    reportfilename="Estuary-Test_Report-%s.pdf"%(curr_date)
    rpt_title = '<para autoLeading="off" fontSize=15 align=center><b>[ Estuary ] Test Report %s</b><br/><br/><br/></para>' %(curr_date)
    story.append(Paragraph(rpt_title,normalStyle))

    rpt_ps = '<para autoLeading="off" fontSize=8 align=center>( This mail is send by Jenkins automatically, don\'t reply )</para>'
    story.append(Paragraph(rpt_ps,normalStyle))

    text = '''<para autoLeading="off" fontSize=12><br /><font color=black>1.General Report</font><br /><br /></para>'''
    story.append(Paragraph(text,normalStyle))

    pieimg = Image('baseinfo_pie.jpg')
    pieimg.drawHeight = 320
    pieimg.drawWidth = 480
    story.append(pieimg)

    test_suite_dict={}
    for job_id in job_result_dict.keys():
        for item in job_result_dict[job_id]:
            if item['suite'] not in test_suite_dict:
                test_suite_dict[item['suite']] = {}
                if item['result'] not in test_suite_dict[item['suite']]:
                    test_suite_dict[item['suite']][item['result']]=1
                else:
                    value=test_suite_dict[item['suite']][item['result']]
                    value=value+1
                    test_suite_dict[item['suite']][item['result']]=value
            else:
                if item['result'] not in test_suite_dict[item['suite']]:
                    test_suite_dict[item['suite']][item['result']]=1
                else:
                    value=test_suite_dict[item['suite']][item['result']]
                    value=value+1
                    test_suite_dict[item['suite']][item['result']]=value
    component_data= [['TestSuite', 'Passes', 'Fails', 'Totals']]
    for test_suite in test_suite_dict.keys():
        passnum=0
        failnum=0
        if 'pass' in test_suite_dict[test_suite]:
            passnum=test_suite_dict[test_suite]['pass']
        if 'fail' in test_suite_dict[test_suite]:
            failnum=test_suite_dict[test_suite]['fail']
        totalnum=passnum+failnum
        data=[test_suite,passnum,failnum,totalnum]
        component_data.append(data)
    #
    component_table = Table(component_data,colWidths=[150,60,60,60])
    #
    component_table.setStyle(TableStyle([
    ('FONTSIZE',(0,0),(-1,-1),8),#font size
    ('BACKGROUND',(0,0),(-1,0), colors.lightskyblue),#
    ('ALIGN',(-1,0),(-2,0),'RIGHT'),#
    ('VALIGN',(-1,0),(-2,0),'MIDDLE'),  #
    ('LINEBEFORE',(0,0),(0,-1),0.1,colors.grey),#
    ('TEXTCOLOR',(0,1),(-2,-1),colors.black),#
    ('GRID',(0,0),(-1,-1),0.5,colors.black),#
    ]))
    story.append(component_table)

    text = '''<para autoLeading="off" fontSize=12><br /><font color=black>2.Test Suite Result Detail</font><br /><br /></para>'''
    story.append(Paragraph(text,normalStyle))
    component_data= [['JobID','Suite', 'Name','Result']]
    for job_id in job_result_dict.keys():
        for item in job_result_dict[job_id]:
            component_data.append([job_id,item['suite'],item['name'],item['result']])

    component_table = Table(component_data)
    component_table.setStyle(TableStyle([
    ('FONTSIZE',(0,0),(-1,-1),8),#font size
    ('BACKGROUND',(0,0),(-1,0), colors.lightskyblue),#
    ('ALIGN',(-1,0),(-2,0),'RIGHT'),#
    ('VALIGN',(-1,0),(-2,0),'MIDDLE'),  #
    ('LINEBEFORE',(0,0),(0,-1),0.1,colors.grey),#
    ('TEXTCOLOR',(0,1),(-2,-1),colors.black),#
    ('GRID',(0,0),(-1,-1),0.5,colors.black),#
    ]))
    story.append(component_table)

    text = '''<para autoLeading="off" fontSize=12><br /><font color=black>3.Different Scope Pass Number</font><br /><br /></para>'''
    story.append(Paragraph(text,normalStyle))

    barimg = Image('baseinfo_bar.jpg')
    barimg.drawHeight = 320
    barimg.drawWidth = 480
    story.append(barimg)


    doc=SimpleDocTemplate('resultfile.pdf')
    doc.build(story)


#by job_result_dict get current test report by zhaofs0921
def generate_current_test_report():
    print "generate_current_test_report"
    suite_list = [] #all test suite list

    test_suite_dict={}
    test_scope_dict={}

#   Statistics of each test suite
    for job_id in job_result_dict.keys():
        for item in job_result_dict[job_id]:
            if item['suite'] not in test_suite_dict:
                test_suite_dict[item['suite']] = {}
                if item['result'] not in test_suite_dict[item['suite']]:
                    test_suite_dict[item['suite']][item['result']]=1
                else:
                    value=test_suite_dict[item['suite']][item['result']]
                    value=value+1
                    test_suite_dict[item['suite']][item['result']]=value
            else:
                if item['result'] not in test_suite_dict[item['suite']]:
                    test_suite_dict[item['suite']][item['result']]=1
                else:
                    value=test_suite_dict[item['suite']][item['result']]
                    value=value+1
                    test_suite_dict[item['suite']][item['result']]=value
    print_base_info_pie_chart(test_suite_dict,"Base Pass Rate Situation Chart")
    workspace=os.getenv("WORKSPACE")
    test_suite_dir=os.path.join(workspace,"local/ci-test-cases")
    test_suite_scope_dict = {}
    for job_id in job_result_dict.keys():
        for item in job_result_dict[job_id]:
            if 'metadata' in item:
                metadata = item['metadata']
                if 'path' in metadata and 'repository' in metadata:
                    count_scope_pass_number(test_suite_scope_dict,metadata['path'],item['result'])
                elif 'extra' in metadata:
                    path=""
                    repository=""
                    for extra in metadata['extra']:
                        if 'path' in extra :
                            path=extra['path']
                            continue
                        if 'repository' in extra:
                            repository=extra['repository']
                            continue
                    if path != "" and repository != "":
                        count_scope_pass_number(test_suite_scope_dict,path,item['result'])
#    print test_suite_scope_dict
    print_scope_info_bar_chart(test_suite_scope_dict,"Pass Number Bar Chart")
    create_test_report_pdf(job_result_dict)

    current_test_result_dir = os.getcwd()
    test_result_file_name = "test_result_dict.txt"
    test_result_file = os.path.join(current_test_result_dir,test_result_file_name)
    if os.path.exists(test_result_file):
        os.remove(test_result_file)
    with open(test_result_file, 'w') as wfp:
        wfp.write(str(job_result_dict))


def count_scope_pass_number(test_suite_scope_dict,path,result):
    workspace=os.getenv("WORKSPACE")
    test_suite_dir=os.path.join(workspace,"local/ci-test-cases")
    yaml_file=utils.load_yaml(os.path.join(test_suite_dir,path))
    for scope in yaml_file['metadata']['scope']:
        if result == 'pass':
            if scope not in test_suite_scope_dict:
                test_suite_scope_dict[scope]=1
            else:
                value=test_suite_scope_dict[scope]
                value = value+1
                test_suite_scope_dict[scope] = value


def generate_history_test_report():
    print "generate_history_test_report"


def boot_report(config):
    connection, jobs, duration =  parse_yaml(config.get("boot"))
    # TODO: Fix this when multi-lab sync is working
    results_directory = os.getcwd() + '/results'
    results = {}
    utils.mkdir(results_directory)
    test_plan = None

    if config.get("lab"):
        report_directory = os.path.join(results_directory, config.get("lab"))
    else:
        report_directory = results_directory

    if os.path.exists(report_directory):
        shutil.rmtree(report_directory)
    utils.mkdir(report_directory)

    for job_id in jobs:
        print 'Job ID: %s' % job_id
        # Init
        boot_meta = {}
        arch = None
        board_instance = None
        boot_retries = 0
        kernel_defconfig_full = None
        kernel_defconfig = None
        kernel_defconfig_base = None
        kernel_version = None
        device_tree = None
        kernel_tree = None
        kernel_addr = None
        initrd_addr = None
        dtb_addr = None
        dtb_append = None
        job_file = ''
        board_offline = False
        kernel_boot_time = None
        boot_failure_reason = None
        efi_rtc = False
        # Retrieve job details
        device_type = ''
        job_details = connection.scheduler.job_details(job_id)
        if job_details['requested_device_type_id']:
            device_type = job_details['requested_device_type_id']
        if job_details['description']:
            job_name = job_details['description']
            try:
                job_short_name = re.search(".*?([A-Z]+.*)", job_name).group(1)
            except Exception:
                job_short_name = 'boot-test'
        try:
            device_name = job_details['_actual_device_cache']['hostname']
        except Exception:
            continue
        result = jobs[job_id]['result']
        bundle = jobs[job_id]['bundle']
        if not device_type:
            device_type = job_details['_actual_device_cache']['device_type_id']
        try:
            binary_job_file = connection.scheduler.job_output(job_id)
        except xmlrpclib.Fault:
            print 'Job output not found for %s' % device_type
            continue
        # Parse LAVA messages out of log
        raw_job_file = str(binary_job_file)
        for line in raw_job_file.splitlines():
            if 'Infrastructure Error:' in line:
                print 'Infrastructure Error detected!'
                index = line.find('Infrastructure Error:')
                boot_failure_reason = line[index:]
                board_offline = True
            if 'Bootloader Error:' in line:
                print 'Bootloader Error detected!'
                index = line.find('Bootloader Error:')
                boot_failure_reason = line[index:]
                board_offline = True
            if 'Kernel Error:' in line:
                print 'Kernel Error detected!'
                index = line.find('Kernel Error:')
                boot_failure_reason = line[index:]
            if 'Userspace Error:' in line:
                print 'Userspace Error detected!'
                index = line.find('Userspace Error:')
                boot_failure_reason = line[index:]
            if '<LAVA_DISPATCHER>' not in line:
                if len(line) != 0:
                    job_file += line + '\n'
            if 'rtc-efi rtc-efi: setting system clock to' in line:
                if device_type == 'dynamic-vm':
                    efi_rtc = True
        if not kernel_defconfig or not kernel_version or not kernel_tree:
            try:
                job_metadata_info = connection.results.get_testjob_metadata(job_id)
                kernel_defconfig = utils.get_value_by_key(job_metadata_info,'kernel_defconfig')
                kernel_version = utils.get_value_by_key(job_metadata_info,'kernel_version')
                kernel_tree = utils.get_value_by_key(job_metadata_info,'kernel_tree')
                device_tree = utils.get_value_by_key(job_metadata_info,'device_tree')
            except Exception:
                continue

        # Record the boot log and result
        # TODO: Will need to map device_types to dashboard device types
        if kernel_defconfig and device_type and result:
            if ( 'arm' == arch or 'arm64' == arch ) and device_tree is None:
                platform_name = device_map[device_type][0] + ',legacy'
            else:
                if test_plan == 'boot-nfs' or test_plan == 'boot-nfs-mp':
                    platform_name = device_map[device_type][0] + '_rootfs:nfs'
                else:
                    platform_name = device_map[device_type][0]

            # Create txt format boot metadata
            print 'Creating boot log for %s' % (platform_name + job_name + '_' + job_id)
            log = 'boot-%s.txt' % (platform_name + job_name + '_' + job_id)
            if config.get("lab"):
                directory = os.path.join(results_directory, kernel_defconfig + '/' + config.get("lab"))
            else:
                directory = os.path.join(results_directory, kernel_defconfig)
            utils.ensure_dir(directory)

            utils.write_file(job_file, log, directory)

            if kernel_boot_time is None:
                kernel_boot_time = '0.0'
            if results.has_key(kernel_defconfig):
                results[kernel_defconfig].append({'device_type': platform_name,
                    'job_id': job_id, 'job_name': job_short_name,
                    'kernel_boot_time': kernel_boot_time, 'result': result,
                    'device_name': device_name})
            else:
                results[kernel_defconfig] = [{'device_type': platform_name,
                    'job_id': job_id, 'job_name': job_short_name,
                    'kernel_boot_time': kernel_boot_time, 'result': result,
                    'device_name': device_name}]

            # Create JSON format boot metadata
            print 'Creating JSON format boot metadata'
            if config.get("lab"):
                boot_meta['lab_name'] = config.get("lab")
            else:
                boot_meta['lab_name'] = None
            if board_instance:
                boot_meta['board_instance'] = board_instance
            boot_meta['retries'] = boot_retries
            boot_meta['boot_log'] = log
            # TODO: Fix this
            boot_meta['version'] = '1.0'
            boot_meta['arch'] = arch
            boot_meta['defconfig'] = kernel_defconfig_base
            if kernel_defconfig_full is not None:
                boot_meta['defconfig_full'] = kernel_defconfig_full
            if device_map[device_type][1]:
                boot_meta['mach'] = device_map[device_type][1]
            boot_meta['kernel'] = kernel_version

            boot_meta['job'] = kernel_tree
            boot_meta['board'] = platform_name
            if board_offline and result == 'FAIL':
                boot_meta['boot_result'] = 'OFFLINE'
                #results[kernel_defconfig]['result'] = 'OFFLINE'
            else:
                boot_meta['boot_result'] = result
            if result == 'FAIL' or result == 'OFFLINE':
                if boot_failure_reason:
                    boot_meta['boot_result_description'] = boot_failure_reason
                else:
                    boot_meta['boot_result_description'] = 'Unknown Error: platform failed to boot'
            boot_meta['boot_time'] = kernel_boot_time
            # TODO: Fix this
            boot_meta['boot_warnings'] = None
            if device_tree:
                if arch == 'arm64':
                    boot_meta['dtb'] = 'dtbs/' + device_map[device_type][1] + '/' + device_tree
                else:
                    boot_meta['dtb'] = 'dtbs/' + device_tree
            else:
                boot_meta['dtb'] = device_tree
            boot_meta['dtb_addr'] = dtb_addr
            boot_meta['dtb_append'] = dtb_append
            # TODO: Fix this
            boot_meta['initrd'] = None
            boot_meta['initrd_addr'] = initrd_addr
            if arch == 'arm':
                boot_meta['kernel_image'] = 'zImage'
            elif arch == 'arm64':
                boot_meta['kernel_image'] = 'Image'
            else:
                boot_meta['kernel_image'] = 'bzImage'
            boot_meta['loadaddr'] = kernel_addr
            json_file = 'boot-%s.json' % (platform_name + job_name + '_' + job_id)
            utils.write_json(json_file, directory, boot_meta)
            # add by wuyanjun
            parser_and_get_result(job_file, log, directory, report_directory, connection)

            #try to generate test_summary
            generate_test_report(job_id, connection)

    if results and kernel_tree and kernel_version:
        print 'Creating summary for %s' % (kernel_version)
        boot = '%s-boot-report.txt' % (kernel_version)
        if test_plan and ('boot' in test_plan or 'BOOT' in test_plan):
            boot = boot.replace('boot', test_plan)
        passed = 0
        failed = 0
        for defconfig, results_list in results.items():
            for result in results_list:
                if result['result'] == 'PASS':
                    passed += 1
                else:
                    failed += 1
        total = passed + failed
        with open(os.path.join(report_directory, boot), 'a') as f:
            f.write('Subject: %s boot: %s boots: %s passed, %s failed (%s)\n' % (kernel_tree,
                                                                                str(total),
                                                                                str(passed),
                                                                                str(failed),
                                                                                kernel_version))
            f.write('\n')
            f.write('Total Duration: %.2f minutes\n' % (duration / 60))
            f.write('Tree/Branch: %s\n' % kernel_tree)
            f.write('Git Describe: %s\n' % kernel_version)
            first = True
            for defconfig, results_list in results.items():
                for result in results_list:
                    if result['result'] == 'OFFLINE':
                        if first:
                            f.write('\n')
                            f.write('Boards Offline:\n')
                            first = False
                        f.write('\n')
                        f.write(defconfig)
                        f.write('\n')
                        break
                for result in results_list:
                    if result['result'] == 'OFFLINE':
                        f.write('    %s   %s   %s   %ss   %s: %s\n' % (result['job_id'],
                                                                    result['device_type'],
                                                                    result['device_name'],
                                                                    result['kernel_boot_time'],
                                                                    result['job_name'],
                                                                    result['result']))
                        f.write('\n')
            first = True
            for defconfig, results_list in results.items():
                for result in results_list:
                    if result['result'] == 'FAIL':
                        if first:
                            f.write('\n')
                            f.write('Failed Boot Tests:\n')
                            first = False
                        f.write('\n')
                        f.write(defconfig)
                        f.write('\n')
                        break
                for result in results_list:
                    if result['result'] == 'FAIL':
                        f.write('    %s   %s   %s   %ss   %s: %s\n' % (result['job_id'],
                                                                    result['device_type'],
                                                                    result['device_name'],
                                                                    result['kernel_boot_time'],
                                                                    result['job_name'],
                                                                    result['result']))
            f.write('\n')
            f.write('Full Boot Report:\n')
            for defconfig, results_list in results.items():
                f.write('\n')
                f.write(defconfig)
                f.write('\n')
                for result in results_list:
                    f.write('    %s   %s   %s   %ss   %s: %s\n' %
                                                                    (result['job_id'],
                                                                        result['device_type'],
                                                                        result['device_name'],
                                                                        result['kernel_boot_time'],
                                                                        result['job_name'],
                                                                        result['result']))


def generate_email_test_report():
    print "--------------now begin get testjob: result ------------------------------"

    suite_list = [] #all test suite list
    case_dict = {} #testcast dict value like 'smoke-test':[test-case1,test-case2,test-case3]
    boot_total = 0
    boot_success = 0
    boot_fail = 0
    test_total = 0
    test_success = 0
    test_fail = 0

    #get all the test suite list from get_testjob_results_yaml
    for job_id in job_result_dict.keys():
        for item in job_result_dict[job_id]:
            if suite_list.count(item['suite']) == 0:
                suite_list.append(item['suite'])

    #inital a no value dict
    for suite in suite_list:
        case_dict[suite] = []

    #set all the value in dict
    for job_id in job_result_dict.keys():
        for item in job_result_dict[job_id]:
            case_dict[item['suite']].append(item)

    # try to write details file
    details_dir = os.getcwd()
    details_file = os.path.join(details_dir, details_summary_name)

    if os.path.exists(details_file):
        os.remove(details_file)
    with open(details_file, "wt") as wfp:
        wfp.write("*" * 24 + " DETAILS TESTCASE START " + "*" * 24 + '\n')
        wfp.write("suite_name\t" + "case_name\t\t" + "case_result\t" + '\n')

    for key in case_dict.keys():
        if key == 'lava':
            for item in case_dict[key]:
                if item['result'] == 'pass':
                    boot_total += 1
                    boot_success += 1
                elif item['result'] == 'fail':
                    boot_total += 1
                    boot_fail += 1
                else:
                    boot_total += 1
        else:
            for item in case_dict[key]:
                if item['result'] == 'pass':
                    test_total += 1
                    test_success += 1
                elif item['result'] == 'fail':
                    test_total += 1
                    test_fail += 1
                else:
                    test_total += 1
                with open(details_file, "at") as wfp:
                    wfp.write(item['suite'] + '\t' + item['name'] + '\t\t' + item['result'] + '\n')
    with open(details_file, "at") as wfp:
        wfp.write("*" * 24 + " DETAILS TESTCASE END " + "*" * 24 + '\n')

    #try to write summary file
    summary_dir = os.getcwd()
    summary_file = os.path.join(summary_dir, whole_summary_name)
    if os.path.exists(summary_file):
        os.remove(summary_file)
    with open(summary_file, 'w') as wfp:
        wfp.write("*" * 20 + " BOOT SUMMARY START " + "*" * 20 + '\n')
        wfp.write("\n" + total_str + str(boot_total))
        wfp.write("\n" + fail_str + str(boot_fail))
        wfp.write("\n" + suc_str + str(boot_success))
        wfp.write("\n" + "*" * 20 + " BOOT SUMMARY END" + "*" * 20 + '\n')

    with open(summary_file, "ab") as wfp:
        wfp.write("*" * 20 + " SUMMARY TESTCASE START " + "*" * 20 + '\n')
        wfp.write("\n" + total_str + str(test_total))
        wfp.write("\n" + fail_str + str(test_fail))
        wfp.write("\n" + suc_str + str(test_success))
        wfp.write("\n" + "*" * 20 + " SUMMARY END " + "*" * 20 + '\n')

    print "--------------now end get testjob result ------------------------------"

def main(args):
    config = configuration.get_config(args)

    if config.get("boot"):
        boot_report(config)
        generate_email_test_report()
        generate_current_test_report()
        generate_history_test_report()

    exit(0)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--boot", help="creates a kernel-ci boot report from a given json file")
    parser.add_argument("--lab", help="lab id")

    args = vars(parser.parse_args())
    main(args)
