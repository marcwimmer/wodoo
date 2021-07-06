*** Settings ***
Documentation     Imports Orders from Magento2 (mocked)
Resource          keywords/odoo_11_ee.robot
Resource          keywords/odoo_env.robot
Resource          keywords/tools.robot
Test Setup        Setup Tests


*** Keywords ***

Import Order From Magento  [Arguments]
                            ...  ${name}
	${order}=                     tools.get_json_content       tests/data/magento2_orders/${name}.json 
    Log                           ${order}

	Log                           To simulate a new customer we remove existing partner_ids
	Log                           The ids are taken from the magento import json.
    # TODO Sasa update ids that are used in the json
	Run Keyword If                ${order['extension_attributes']['shipping_assignments'][0]['shipping']['address'].get('customer_address_id')}    Odoo Exec Sql                 update res_partner set mage2_address_id = null where mage2_address_id in (${order['extension_attributes']['shipping_assignments'][0]['shipping']['address']['customer_address_id']});
	Odoo Exec Sql                 update res_partner set mage2_address_id = null where mage2_address_id in (${order['billing_address_id']});

	Run Keyword If                ${order['billing_address'].get('customer_addres_id')}    Odoo Exec Sql                 update res_partner set mage2_address_id = null where mage2_address_id in (${order['billing_address']['customer_address_id']});


	${key}=                       Get Now As String
	${order_name}=                Set Variable             ${CURRENT_TEST}-${key}
	Log                           Overwrite increment_id of source json file (from magento coming)
	Set To Dictionary             ${order}  increment_id  ${order_name}
	Log                           Ordernumber will be: ${order['increment_id']}
	Odoo Put Dict As File         ${order}               /tmp/order.json
	${kwargs}=                    Create Dictionary      filepath=/tmp/order.json
	${sale_order_id}=             Odoo Execute           sale.order  import_magento2order_from_file  kwparams=${kwargs}
	Log                           This is the sale order id ${sale_order_id}
	Odoo Execute                  sale.order  action_confirm  ${sale_order_id}
	Log                           This is the saleorder id ${sale_order_id}
	Odoo Execute                  sale.order  action_invoice_create  ${sale_order_id}
    [return]                      ${sale_order_id}

Import Second Magento Order  [Arguments]
                            ...  ${name2}
    ${order2}=                     tools.get_json_content       tests/data/magento2_orders/${name2}.json
    Log                           ${order2}

	${key2}=                      Get Now As String
	${order_name2}=               Set Variable             ${CURRENT_TEST}-${key2}
	Log                           Overwrite increment_id of source json file (from magento coming)
	Set To Dictionary             ${order2}  increment_id  ${order_name2}
	Log                           Ordernumber will be: ${order2['increment_id']}
	Odoo Put Dict As File         ${order2}               /tmp/order.json
	${kwargs}=                    Create Dictionary      filepath=/tmp/order.json
	${sale_order_id2}=             Odoo Execute           sale.order  import_magento2order_from_file  kwparams=${kwargs}
	Log                           This is the sale order id ${sale_order_id2}
	Odoo Execute                  sale.order  action_confirm  ${sale_order_id2}
	Log                           This is the saleorder id ${sale_order_id2}
	Odoo Execute                  sale.order  action_invoice_create  ${sale_order_id2}
    [return]                      ${sale_order_id2}

Make Carrier File                 [Arguments]
                                  ...  ${picking_id}
	Go To                         ${ODOO_URL}/web#id=${picking_id}&view_type=form&model=stock.picking
    Wait Until Element Is Visible  xpath=//span[contains(@class, 'o_field_char')]
    Capture Page Screenshot
    SideBarAction                 Action  Generate Carrier Files
    Sleep                         3s
    Capture Page Screenshot
    Wait Until Element Is Visible  //div[@data-bt-testing-model_name='delivery.carrier.file.generate']
    Click Element                 //div[@data-bt-testing-model_name='delivery.carrier.file.generate']/input[@type='checkbox']
    Capture Page Screenshot
    ${picking}=                   Odoo Read                     stock.picking  ${picking_id}  name
    Log                           ${picking}
    ${now}=                       Set Variable  ${{datetime.datetime.utcnow()}}
    Click Button                  xpath=//button[@name='action_generate']
	Sleep                         3s
    ${carrier_file}=              Odoo Get Latest File In Folder     /mnt_host/carrierfiles  **/${picking['name'].replace('/', '')}*  ${now}  1
    [return]                      ${carrier_file}

*** Test Cases ***
001 Test Import Order - Company in Delivery Address - Make sure firstname/lastname is in Label
    ${sale_order_id}=             Import Order From Magento     dhl - test_order_firstname_lastname_in_shipping_address
    
	${sale_order}=                Odoo Read                   sale.order      ${sale_order_id}  picking_ids
    ${pickings}=                  Odoo Read                   stock.picking   ${sale_order[0]['picking_ids']}  name
    ${pickings}=                  Odoo Search Read            stock.picking  [('id', 'in', ${sale_order[0]['picking_ids']}), ('name', 'ilike', 'OUT')]  name,partner_id,contact_id

    Log                           Reading Partner and contact Address
    ${partner}=                   Odoo Read                   res.partner    ${pickings[0]['partner_id'][0]}  name,firstname,lastname
    ${contact}=                   Odoo Read                   res.partner    ${pickings[0]['contact_id'][0]}  name,firstname,lastname

    Log                           This is partner: ${partner}
    Log                           This is contact: ${contact}
    Should Be Equal               ${contact['firstname']}  Shipping Firstname
    Should Be Equal               ${contact['lastname']}   Shipping Lastname
    
	Login
	Go To                         ${ODOO_URL}/web#id=${sale_order_id[0]}&view_type=form&model=sale.order
    Wait Until Element Is Visible  xpath=//span[contains(@class, 'o_field_char')]
    Capture Page Screenshot

    ${carrier_file}=              Make Carrier File  ${pickings[0]['id']}
    Log                           ${carrier_file}
    Should Contain                ${carrier_file}  Shipping Firstname
    Should Contain                ${carrier_file}  Shipping Lastname


002 Test Import Order - Packing Location
    ${sale_order_id}=                Import Order From Magento     dhl - test_order_packstation_in_shipping_address
    
	${sale_order}=                Odoo Read                   sale.order      ${sale_order_id}  picking_ids
    ${pickings}=                  Odoo Read                   stock.picking   ${sale_order[0]['picking_ids']}  name
    ${pickings}=                  Odoo Search Read            stock.picking  [('id', 'in', ${sale_order[0]['picking_ids']}), ('name', 'ilike', 'OUT')]  name,partner_id,contact_id

    Log                           Reading Partner and contact Address
    ${partner}=                   Odoo Read                   res.partner    ${pickings[0]['partner_id'][0]}  name,firstname,lastname
    ${contact}=                   Odoo Read                   res.partner    ${pickings[0]['contact_id'][0]}  name,firstname,lastname

    Log                           This is partner: ${partner}
    Log                           This is contact: ${contact}
    Should Be Equal               ${contact['firstname']}  Shipping Firstname
    Should Be Equal               ${contact['lastname']}   Shipping Lastname
    
	Login
	Go To                         ${ODOO_URL}/web#id=${sale_order_id[0]}&view_type=form&model=sale.order
    Wait Until Element Is Visible  xpath=//span[contains(@class, 'o_field_char')]
    Capture Page Screenshot

    ${carrier_file}=              Make Carrier File            ${pickings[0]['id']}
    Log                           ${carrier_file}
    Should Contain                ${carrier_file}  Shipping Firstname
    Should Contain                ${carrier_file}  Shipping Lastname

003 Test Import Order - Shiping address changed for same customer
    ${sale_order_id}=             Import Order From Magento     dhl - test_order_firstname_lastname_in_shipping_address

	Log                           To simulate a address changed we import second order without remove partner_ids
    ${sale_order_id2}=            Import Second Magento Order   dhl - test_order_change_lastname_in_shipping_address

	${sale_order}=                Odoo Read                   sale.order      ${sale_order_id2}  picking_ids
    ${pickings}=                  Odoo Read                   stock.picking   ${sale_order[0]['picking_ids']}  name
    ${pickings}=                  Odoo Search Read            stock.picking  [('id', 'in', ${sale_order[0]['picking_ids']}), ('name', 'ilike', 'OUT')]  name,partner_id,contact_id

    Log                           Reading Partner and contact Address
    ${partner}=                   Odoo Read                   res.partner    ${pickings[0]['partner_id'][0]}  name,firstname,lastname
    ${contact}=                   Odoo Read                   res.partner    ${pickings[0]['contact_id'][0]}  name,firstname,lastname

    Log                           This is partner: ${partner}
    Log                           This is contact: ${contact}
    Should Be Equal               ${contact['firstname']}  Shipping Firstname Changed
    Should Be Equal               ${contact['lastname']}   Shipping Lastname Changed
    Capture Page Screenshot


004 Test Import Order - Optional Info in Address
    ${sale_order_id}=             Import Order From Magento     hermes - optional_address_shipping_and_billing
    
	${sale_order}=                Odoo Read                   sale.order      ${sale_order_id}  picking_ids
    ${pickings}=                  Odoo Read                   stock.picking   ${sale_order[0]['picking_ids']}  name
    ${pickings}=                  Odoo Search Read            stock.picking  [('id', 'in', ${sale_order[0]['picking_ids']}), ('name', 'ilike', 'OUT')]  name,partner_id,contact_id

    Log                           Reading Partner and contact Address
    ${partner}=                   Odoo Read                   res.partner    ${pickings[0]['partner_id'][0]}  name,firstname,lastname
    ${contact}=                   Odoo Read                   res.partner    ${pickings[0]['contact_id'][0]}  name,firstname,lastname

    Log                           This is partner: ${partner}
    Log                           This is contact: ${contact}
    Should Be Equal               ${contact['firstname']}  Shipping Firstname
    Should Be Equal               ${contact['lastname']}   Shipping Lastname
    
	Login
	Go To                         ${ODOO_URL}/web#id=${sale_order_id[0]}&view_type=form&model=sale.order
    Wait Until Element Is Visible  xpath=//span[contains(@class, 'o_field_char')]
    Capture Page Screenshot

    ${carrier_file}=              Make Carrier File            ${pickings[0]['id']}
    Log                           ${carrier_file}
    Should Contain                ${carrier_file}  Shipping Firstname
    Should Contain                ${carrier_file}  Shipping Lastname

005 Test Discount Percent
    [Documentation]               Magento seems to have a bug: discount percent is 0 but there is a discount amount;
    ...                           They are import wrong at the moment.
    ${sale_order_id}=             Import Order From Magento     dhl - order_discount_percent_is_non_zero
    
	${sale_order}=                Odoo Read                   sale.order      ${sale_order_id}  picking_ids
    ${pickings}=                  Odoo Read                   stock.picking   ${sale_order[0]['picking_ids']}  name
    ${pickings}=                  Odoo Search Read            stock.picking  [('id', 'in', ${sale_order[0]['picking_ids']}), ('name', 'ilike', 'OUT')]  name,partner_id,contact_id

    Log                           Reading Partner and contact Address
    ${partner}=                   Odoo Read                   res.partner    ${pickings[0]['partner_id'][0]}  name,firstname,lastname
    ${contact}=                   Odoo Read                   res.partner    ${pickings[0]['contact_id'][0]}  name,firstname,lastname

    Log                           This is partner: ${partner}
    Log                           This is contact: ${contact}
    Should Be Equal               ${contact['firstname']}  Shipping Firstname
    Should Be Equal               ${contact['lastname']}   Shipping Lastname
    
	Login
	Go To                         ${ODOO_URL}/web#id=${sale_order_id[0]}&view_type=form&model=sale.order
    Wait Until Element Is Visible  xpath=//span[contains(@class, 'o_field_char')]
    Capture Page Screenshot

    ${carrier_file}=              Make Carrier File            ${pickings[0]['id']}
    Log                           ${carrier_file}
    Should Contain                ${carrier_file}  Shipping Firstname
    Should Contain                ${carrier_file}  Shipping Lastname

006 Test Import Order - Where name of commpany has postnummer
    ${sale_order_id}=                Import Order From Magento     dhl - order_postnummer_in_company_name

	${sale_order}=                Odoo Read                   sale.order      ${sale_order_id}  picking_ids
    ${pickings}=                  Odoo Read                   stock.picking   ${sale_order[0]['picking_ids']}  name
    ${pickings}=                  Odoo Search Read            stock.picking  [('id', 'in', ${sale_order[0]['picking_ids']}), ('name', 'ilike', 'OUT')]  name,partner_id,contact_id

    Log                           Reading Partner and contact Address
    ${partner}=                   Odoo Read                   res.partner    ${pickings[0]['partner_id'][0]}  street,street2
    ${contact}=                   Odoo Read                   res.partner    ${pickings[0]['contact_id'][0]}  street,street2

    Log                           This is partner: ${partner}
    Log                           This is contact: ${contact}
    Should Be Equal               ${contact['street2']}  946355642
    Should Be Equal               ${contact['street']}   Packstation 191

	Login
	Go To                         ${ODOO_URL}/web#id=${sale_order_id[0]}&view_type=form&model=sale.order
    Wait Until Element Is Visible  xpath=//span[contains(@class, 'o_field_char')]
    Capture Page Screenshot

    ${carrier_file}=              Make Carrier File            ${pickings[0]['id']}
    Log                           ${carrier_file}
    Should Contain                ${carrier_file}  946355642
    Should Contain                ${carrier_file}  Packstation

006 Test Wrong Total Put into DHL File
    [Documentation]               Making sure, that gross amount is put into dhl file.
    ${sale_order_id}=             Import Order From Magento     1001968273
    
	${sale_order}=                Odoo Read                   sale.order      ${sale_order_id}  amount_total,picking_ids
    Log                           Amount Total is ${sale_order[0]['amount_total']}
    Should Be Equal As Strings    ${sale_order[0]['amount_total']}  48.6

    Login
	Go To                         ${ODOO_URL}/web#id=${sale_order_id[0]}&view_type=form&model=sale.order
    Wait Until Element Is Visible  xpath=//span[contains(@class, 'o_field_char')]
    Capture Page Screenshot

    ${pickings}=                  Odoo Read                   stock.picking   ${sale_order[0]['picking_ids']}  name
    ${carrier_file}=              Make Carrier File            ${pickings[0]['id']}
    Log                           ${carrier_file}
    Should Contain                ${carrier_file}  48.60

007 Import not regularly imported dont know why yet
    [Documentation]               Making sure, that gross amount is put into dhl file.
    ${sale_order_id}=             Import Order From Magento     1001968273
    
	${sale_order}=                Odoo Read                   sale.order      ${sale_order_id}  amount_total,picking_ids
    Log                           Amount Total is ${sale_order[0]['amount_total']}
    Should Be Equal As Strings    ${sale_order[0]['amount_total']}  48.6

    Login
	Go To                         ${ODOO_URL}/web#id=${sale_order_id[0]}&view_type=form&model=sale.order
    Wait Until Element Is Visible  xpath=//span[contains(@class, 'o_field_char')]
    Capture Page Screenshot

    ${pickings}=                  Odoo Read                   stock.picking   ${sale_order[0]['picking_ids']}  name
    ${carrier_file}=              Make Carrier File            ${pickings[0]['id']}
    Log                           ${carrier_file}
    Should Contain                ${carrier_file}  48.60

008 
    [Documentation]               Making sure, that gross amount is put into dhl file.
    ${sale_order_id}=             Import Order From Magento     1001968273
    
	${sale_order}=                Odoo Read                   sale.order      ${sale_order_id}  amount_total,picking_ids
    Log                           Amount Total is ${sale_order[0]['amount_total']}
    Should Be Equal As Strings    ${sale_order[0]['amount_total']}  67.45
    Should Be Equal As Strings    ${sale_order[0]['amount_tax']}  4.87

    Login
	Go To                         ${ODOO_URL}/web#id=${sale_order_id[0]}&view_type=form&model=sale.order
    Wait Until Element Is Visible  xpath=//span[contains(@class, 'o_field_char')]
    Capture Page Screenshot

    ${pickings}=                  Odoo Read                   stock.picking   ${sale_order[0]['picking_ids']}  name
    ${carrier_file}=              Make Carrier File            ${pickings[0]['id']}
    Log                           ${carrier_file}
    Should Contain                ${carrier_file}  67.45

009 
    [Documentation]               Making sure, that gross amount is put into dhl file.
    [Tags]                        current
    ${sale_order_id}=             Import Order From Magento     1002002476
    
	${sale_order}=                Odoo Read                   sale.order      ${sale_order_id}  amount_total,picking_ids
    Log                           Amount Total is ${sale_order[0]['amount_total']}
    Should Be Equal As Strings    ${sale_order[0]['amount_total']}  21.8