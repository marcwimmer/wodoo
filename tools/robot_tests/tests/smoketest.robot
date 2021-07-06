*** Settings ***
Documentation     Smoketest
Resource          keywords/odoo_11_ee.robot
Test Setup        Setup Smoketest


*** Keywords ***

*** Test Cases ***
Smoketest
    Search for the admin

*** Keywords ***
Setup Smoketest
    Login

Search for the admin
    Odoo Search                     model=res.users  domain=[]  count=False
    ${count}=  Odoo Search          model=res.users  domain=[('login', '=', 'admin')]  count=True
    Should Be Equal As Strings      ${count}  1
    Log To Console  ${count}
