*** Settings ***
Library                    ../library/odoo.py
Library                    ../library/tools.py
*** Variables ***
${XMLID_DEFAULT_MODULE}    robot_tests

*** Keywords ***
Setup Tests
    ${CURRENT_TEST}=                 Technical Testname  ${TEST NAME}
    Set Suite Variable               ${CURRENT_TEST}
