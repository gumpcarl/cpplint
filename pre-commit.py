#!/usr/bin/env python3

import os
import sys
import codecs
import subprocess
import pkg_resources

required = {'pandas'}
installed = {pkg.key for pkg in pkg_resources.working_set}
missing = required - installed
if len(missing) != 0:
    print("Fail to commit. Please install pandas manually and commit again.\n$ pip3 install pandas")
    sys.exit(1)

import pandas as pd
import cpplint


ignore_check_key_words = ['3rd_party', 'APA_Dependencies', 'hdmap']


def is_valid_src(filename):
    for key in ignore_check_key_words:
        if not os.path.isfile(filename) or not filename.endswith(
                ('.h', '.hh', '.hpp', '.c', '.cc', '.cpp')) or key in filename:
            return False
    return True


def is_new_or_modified(x):
    if x.startswith("??") or x.startswith("M"):
        return True
    return False


def is_added(x):
    if x.startswith("A"):
        return True
    return False


def main():
    exec_cmd = subprocess.run(["git", "diff-index", "--name-status", "HEAD", "--cached"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    cmd_return = exec_cmd.stdout.decode('utf-8')
    filenames_total = cmd_return.split('\n')
    filenames = [x.split('\t')[-1] for x in filenames_total if x.strip()]
    args = ['--v=0']
    args.extend(filenames)

    exit_code = 1
    # Change stderr to write with replacement characters so we don't die
    # if we try to print something containing non-ASCII characters.
    sys.stderr = codecs.StreamReader(sys.stderr, 'replace')
    lint_file_name = '.lint.df'
    cpplint.get_state().ResetErrorCounts()
    if os.path.exists(lint_file_name) and len(filenames) > 0:
        filenames = cpplint.ParseArguments(args)
        for filename in filenames:
            if not is_valid_src(filename):
                continue
            cpplint.ProcessFile(filename, cpplint.get_state().verbose_level)
        if not cpplint.get_state().quiet or cpplint.get_state().error_count > 0:
            cpplint.get_state().PrintErrorCounts()

        # If --quiet is passed, suppress printing error count unless there are errors.
        new_category_count = cpplint.get_state().error_detail.groupby(['filename', 'category']).size()
        # new_categorys_count = new_categorys.value_counts()

        older_category_count = pd.read_pickle(lint_file_name)
        new_cat_error = pd.DataFrame(columns=["filename", "category", 'old_error', 'new_error'])
        update_category_count = False
        for new_cat in new_category_count.index:
            if new_cat in older_category_count.index:
                if older_category_count[new_cat] < new_category_count[new_cat]:
                    new_cat_error = new_cat_error.append({"filename": new_cat[0],
                                                          "category": new_cat[1],
                                                          'old_error': older_category_count[new_cat],
                                                          'new_error': new_category_count[new_cat]},
                                                         ignore_index=True)
                elif older_category_count[new_cat] > new_category_count[new_cat]:
                    update_category_count = True
                    older_category_count[new_cat] = new_category_count[new_cat]
            else:
                new_cat_error = new_cat_error.append({"filename": new_cat[0],
                                                      "category": new_cat[1],
                                                      'old_error': 0,
                                                      'new_error': new_category_count[new_cat]}, ignore_index=True)
        exit_code = new_cat_error.size
        if not new_cat_error.empty:
            print("检测到增量代码错误增加\n")
            print(new_cat_error.to_string())
        elif update_category_count:
            older_category_count.to_pickle(lint_file_name)

    elif not os.path.exists(lint_file_name):
        print('It will cost some seconds to init. Please wait.')
        exec_cmd = subprocess.run(["git", "ls-files"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        cmd_return = exec_cmd.stdout.decode('utf-8')
        filenames_total = cmd_return.split('\n')
        filenames = [x for x in filenames_total if is_valid_src(x)]
        for filename in filenames:
            if is_valid_src(filename):
                cpplint.ProcessFile(filename, cpplint.get_state().verbose_level)
        if not cpplint.get_state().quiet or cpplint.get_state().error_count > 0:
            cpplint.get_state().PrintErrorCounts()

        new_category_count = cpplint.get_state().error_detail.groupby(['filename', 'category']).size()
        # for new_cat in new_category_count.index:
        #     new_category_count[new_cat] = 0
        new_category_count.to_pickle(lint_file_name)
        exit_code = 0
    else:
        exit_code = 0
    exec_cmd = subprocess.run(["git", "status", '--porcelain', lint_file_name], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=True)
    cmd_return = exec_cmd.stdout.decode('utf-8')
    if is_new_or_modified(cmd_return):
        command = "git add " + lint_file_name
        try:
           exec_cmd = subprocess.run(command, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, check=True, shell=True)
        except subprocess.CalledProcessError as e:
            print("fail to upload lint info '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))

    if exit_code > 0:
        RED = '\033[0;31m'
        NC = '\033[0m'  # No Color
        exit_msg = RED + "Fail to commit because of format {} error. \nPlease clean the format error first and then commit again." + NC
        print(exit_msg.format(exit_code))
        print("Your can check your source code by \n"
              "  $ cd ssd_ws\n"
              "  $ ./src/avp/tools/cpp_lint.py --v=0 src/avp/[your module]/*.cpp [or *.h]")
        sys.exit(exit_code)


if __name__ == '__main__':
    main()
