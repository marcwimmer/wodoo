*** Settings ***

Documentation   Odoo 13 backend keywords.
Library         ../library/browser.py
Library         SeleniumLibrary
Library         ../library/tools.py
Resource        ./odoo_client.robot
Resource        ./styling.robot

*** Keywords ***

Open New Browser    [Arguments]     ${url}
    Set Selenium Speed	            0.5
    Set Selenium Timeout	        ${SELENIUM_TIMEOUT}
    Log To Console    ${url}
    ${browser_id}=                  Get Driver For Browser    headlesschrome    ${CURDIR}${/}..${/}tests/download
    Set Window Size                 1920    1080
    Go To                           ${url}
    Capture Page Screenshot
    [return]    ${browser_id}

Login   [Arguments]     ${user}=${ODOO_USER}    ${password}=${ODOO_PASSWORD}    ${url}=${ODOO_URL}/web/login
    ${browser_id}=                          Open New Browser       ${url}
    # Run Keyword and Ignore error            Click element   //a[@href="/web/login"]
    Capture Page Screenshot
    Wait Until Element is Visible           name=login
    Log To Console                          Input is visible, now entering credentials for user ${user} with password ${password} 
    Execute Javascript                      $("input[name=login]").val('${user}');
    Execute Javascript                      $("input[name=password]").val('${password}');
    Log To Console                          Clicking Login
    Capture Page Screenshot
    Click Button                            xpath=//form[@class='oe_login_form']//button[@type='submit']
    Log To Console                          Clicked login button - waiting
    Capture Page Screenshot
    Wait Until Page Contains Element        xpath=//span[contains(@class, 'oe_topbar_name')]	timeout=15 sec
    ElementPostCheck
    Log To Console                          Logged In - continuing
    [return]    ${browser_id}

DatabaseConnect    [Arguments]    ${db}=${db}    ${odoo_db_user}=${ODOO_DB_USER}    ${odoo_db_password}=${ODOO_DB_PASSWORD}    ${odoo_db_server}=${SERVER}    ${odoo_db_port}=${ODOO_DB_PORT}
		Connect To Database Using Custom Params	psycopg2        database='${db}',user='${odoo_db_user}',password='${odoo_db_password}',host='${odoo_db_server}',port=${odoo_db_port}

ClickMenu    [Arguments]	${menu}
    Wait Until Element is visible       xpath=//a[@data-menu-xmlid='${menu}']
	Click Link	xpath=//a[@data-menu-xmlid='${menu}']
	Wait Until Page Contains Element	xpath=//body[contains(@class, 'o_web_client')]
	ElementPostCheck
	sleep   1

ApplicationMainMenuOverview
    Wait Until Element is visible       xpath=//a[contains(@class, 'o_menu_toggle')]
    Click Element                       jquery:a.o_menu_toggle
    Wait Until Page Contains Element	xpath=//body[contains(@class, 'o_web_client')]
	ElementPostCheck

MainMenu	[Arguments]	${menu}
    Wait Until Element is visible       xpath=//a[@data-menu='${menu}']
	Click Link	xpath=//a[@data-menu='${menu}']
	Wait Until Page Contains Element	xpath=//body[contains(@class, 'o_web_client')]
	ElementPostCheck
	sleep   1

SubMenu	[Arguments]	${menu}
	Wait Until Element is visible       xpath=//a[@data-menu='${menu}']
	${menuisopened}=       Run Keyword And Return Status    Wait Until Element Is Visible       jquery=a[data-menu='${menu}'].oe_menu_opened       2
	Run Keyword Unless     ${menuisopened}                  Click Link                     xpath=//a[@data-menu='${menu}']
	ElementPostCheck
	sleep   1

SubSubMenu	[Arguments]	${menu}
    Wait Until Element is visible       xpath=//a[@data-menu='${menu}']
    Click Element                       xpath=//a[@data-menu='${menu}']
    ElementPostCheck
    sleep   1

SubMenuXMLid    [Arguments]		${Name}
	${MODULE}=              Fetch From Left            ${Name}              .
    ${NAME}=                Fetch From Right           ${Name}              .
    ${SubMenuID}=		    get_menu_res_id	${ODOO_URL}	${db}	${ODOO_USER}	${ODOO_PASSWORD}	${MODULE}	${NAME}
    Run Keyword If          ${SubMenuID}               SubMenu         ${SubMenuID}
    Run Keyword Unless      ${SubMenuID}        Fail    ERROR: Module or Name not correct
    sleep   1

MainMenuXMLid    [Arguments]    ${Name}
	${MODULE}=              Fetch From Left            ${Name}              .
    ${NAME}=                Fetch From Right           ${Name}              .
    ${MainMenuID}=		    get_menu_res_id	${ODOO_URL}	${db}	${ODOO_USER}	${ODOO_PASSWORD}	${MODULE}	${NAME}
    Run Keyword If          ${MainMenuID}               MainMenu         ${MainMenuID}
    Run Keyword Unless      ${MainMenuID}        Fail    ERROR: Module or Name not correct
    sleep   1

SubSubMenuXMLid    [Arguments]    ${Name}
    ${MODULE}=              Fetch From Left            ${Name}              .
    ${NAME}=                Fetch From Right           ${Name}              .
    ${SubSubMenuID}=		get_menu_res_id	${ODOO_URL}	${db}	${ODOO_USER}	${ODOO_PASSWORD}	${MODULE}	${NAME}
    Run Keyword If          ${SubSubMenuID}            SubSubMenu         ${SubSubMenuID}
    Run Keyword Unless      ${SubSubMenuID}        Fail    ERROR: Module or Name not correct
    sleep   1

ChangeView      [Arguments]     ${view}
   Wait Until Element is visible        xpath=//div[contains(@class,'o_cp_switch_buttons')]/button[@data-view-type='${view}']
   Click Element                        xpath=//div[contains(@class,'o_cp_switch_buttons')]/button[@data-view-type='${view}']
   Wait Until Page Contains Element     jquery:div.o_view_manager_content .o_${view}_view
   ElementPostCheck


ElementPostCheck
   # Check that page is not loading
   Run Keyword And Ignore Error     Wait Until Page Contains Element    xpath=//body[not(contains(@class, 'o_loading'))]
   # Check that page is not blocked by RPC Call
   Run Keyword And Ignore Error     Wait Until Page Contains Element    xpath=//body[not(contains(@class, 'oe_wait'))]
   # Check not AJAX request remaining (only longpolling)
   Run Keyword And Ignore Error     Wait For Ajax    1

WriteInTitle                [Arguments]     ${model}    ${fieldname}    ${value}
    # Log To Console    //div[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${fieldname}']/input
    # ElementPreCheck         xpath=//div[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${fieldname}']/input[1]
    Input Text              xpath=//div[@data-bt-testing-name='${fieldname}']/input[1]    ${value}
    ElementPostCheck

WriteInField                [Arguments]     ${model}    ${fieldname}    ${value}
    ElementPreCheck         xpath=//input[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${fieldname}']|textarea[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${fieldname}']
    Input Text              xpath=//input[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${fieldname}']|textarea[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${fieldname}']    ${value}
    ElementPostCheck

ClearField                [Arguments]     ${model}    ${fieldname}
    ElementPreCheck         xpath=//input[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${fieldname}']|textarea[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${fieldname}']
    Clear Element Text              xpath=//input[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${fieldname}']|textarea[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${fieldname}']
    ElementPostCheck

Radio   [Arguments]     ${model}    ${field}    ${value}
	Click Element	 xpath=//div[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']//input[@data-value='${value}']

Button    [Arguments]     ${model}=   ${button_name}=     ${class}=    ${name}=    ${span}=     ${contains}=    ${data_name}=    ${position}=1
    Run Keyword Unless      '${span}' == ''      Click Button    xpath=//button[not(contains(@class, 'o_invisible_modifier'))]//span[contains(text(), '${span}')]/..
    Run Keyword Unless      '${name}' == ''      Click Button    xpath=//button[contains(@name,'${name}')]
    Run Keyword Unless      '${model}' == ''     Click Button    xpath=//button[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${button_name}' and not(contains(@class,'o_form_invisible'))]
    Run Keyword Unless      '${contains}' == ''  Click Button    xpath=//button[contains(text(),'${contains}') and not(contains(@class,'o_invisible_modifier'))]
    Run Keyword Unless      '${class}' == ''     Click Button    xpath=//button[contains(@class,'${class}')]
    Run Keyword Unless      '${data_name}' == '' and ${position} == 1     Click Button    xpath=//div[${position}]/div/div/div/div/button[contains(@data-name,'${data_name}')][${position}]
    ElementPostCheck

Button Modal    [Arguments]    ${span}=    ${footer}=
    # Todo optimize
    Run Keyword Unless      '${footer}' == ''      Click Button    xpath=//footer[contains(@class, ${footer})]//button[not(contains(@class, 'o_invisible_modifier'))]//span[contains(text(), '${span}')]/..
    ElementPostCheck

BackButton
    Click Element    xpath=//li[contains(@class, 'o_back_button')]/*[1]
    ElementPostCheck

ButtonXMLid    [Arguments]		${IR_MODEL_DATA_MODEL}    ${Model}    ${Name}
	${MODULE}=              Fetch From Left            ${Name}              .
    ${NAME}=                Fetch From Right           ${Name}              .
    ${ButtonID}=		    get_button_res_id	${ODOO_URL}	${db}	${ODOO_USER}	${ODOO_PASSWORD}  ${IR_MODEL_DATA_MODEL}  ${MODULE}	${NAME}
    Run Keyword If          ${ButtonID}               Button         model=${Model}  button_name=${ButtonID}

Many2OneSelect    [Arguments]    ${model}    ${field}    ${value}
    ElementPreCheck     xpath=//div[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']//input
    Input Text          jquery:div[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}'] input:visible    ${value}
    Wait Until Page Contains Element    xpath=//ul[contains(@class,'ui-autocomplete') and not(contains(@style,'display: none'))]/li[1]/a[contains(text(), '${value}')]
    Sleep                               3
    Click Link                          xpath=//ul[contains(@class,'ui-autocomplete') and not(contains(@style,'display: none'))]/li[1]/a[contains(text(), '${value}')]
    Textfield Should Contain            xpath=//div[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}' and not(contains(@class, 'o_invisible_modifier'))]//input    ${value}
    ElementPostCheck

Select-Option	[Arguments]	${model}	${field}	${value}
    SelectNotebook  xpath=//select[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']
	Select From List By Value    jquery:select[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}']:visible    ${value}
	ElementPostCheck

NotebookPage    [Arguments]     ${string}
    ElementPostCheck
    Wait Until Element Is Visible    jquery:div.o_notebook li a:contains('${string}'):visible:not(.active)
    Click Element                    jquery:div.o_notebook li a:contains('${string}'):visible:not(.active)

NewOne2Many
    [Arguments]         ${model}   ${field}   ${relation_model}   ${modal}=${FALSE}
    [Documentation]     Create a new entry in a form.
    ...                 - model: model of the record of the form
    ...                 - field: name of the related field
    ...                 - relation_model: model of the related field for the inline case
    ...                     or model of the opened form, when a modal is opened
    ...                 - modal: TRUE for the cases when the creation of the new
    ...                     record is not inline, but in a modal. Default is FALSE

    Wait Until Page Contains Element    jquery:div[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}'] table tfoot
    Run Keyword And Ignore Error        Click Element   jquery:div[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}'] table tfoot

    ${selector}=           Set Variable    div.o_field_x2many[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}'] tr td.o_field_x2many_list_row_add a
    Wait Until Element Is Visible          jquery:${selector}
    Click Link                             jquery:${selector}

    Run Keyword If  ${modal}        Wait Until Element Is Visible   jquery:button[data-bt-testing-model_name='${relation_model}']:contains('Verwerfen')
    Run Keyword If  not ${modal}    Wait Until Element Is Visible   jquery:tr.o_selected_row[data-bt-testing-model_name='${relation_model}']

NewOne2ManyPosition
    [Arguments]         ${model}    ${field}    ${position_button}  ${new_line_number}
    [Documentation]     Create a new entry in a form.
    ...                 - model: model of the record of the form
    ...                 - field: name of the related field
    ...                 - relation_model: model of the related field for the inline case
    ...                     or model of the opened form, when a modal is opened
    ...                 - modal: TRUE for the cases when the creation of the new
    ...                     record is not inline, but in a modal. Default is FALSE
    ${selector}=        Set Variable       div.o_field_x2many[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}'] tr td.o_field_x2many_list_row_add a:nth-child(${position_button})
    Wait Until Element Is Visible          jquery:${selector}
    Click Link                             jquery:${selector}
    Wait Until Element Is Visible          jquery:div.o_field_x2many[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}'] tr:nth-child(${new_line_number}) td.o_list_record_remove button

One2ManySelectRecord	[Arguments]	    ${model_origin}    ${field_name}    ${model}	${field}	${value}
    ${selector}=           Set Variable    div.o_field_x2many_list[data-bt-testing-model_name='${model_origin}'][data-bt-testing-name='${field_name}'] tr td.o_field_x2many_list_row_add a
    Wait Until Element Is Visible          jquery:${selector}
    Click Link                             jquery:${selector}
    Capture Page Screenshot
    Wait Until Page Contains Element    jquery:div[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}'] input.ui-autocomplete-input
    Click Element                        jquery:div[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}'] input.ui-autocomplete-input
    Capture Page Screenshot
    Wait Until Page Contains Element    jquery:li.ui-menu-item:contains('${value}')
    Click Element                       jquery:li.ui-menu-item:contains('${value}')
    Capture Page Screenshot
    ElementPostCheck

SelectListView  [Arguments]    ${model}    @{fields}
    # Initialize variable
    ${xpath}=    Set Variable

    # Got throught all field=value and to select the correct record
    : FOR    ${field}    IN  @{fields}
    # Split the string in fieldname=fieldvalue
    \    ${fieldname}    ${fieldvalue}=    Split String    ${field}    separator==    max_split=1
    \    ${fieldxpath}=    Catenate    @data-bt-testing-model_name='${model}' and @data-field='${fieldname}'

         # We first check if this field is in the view and visible
         # otherwise a single field can break the whole command

    \    ${checkxpath}=     Catenate    (//table[contains(@class,'oe_list_content')]//tr[descendant::td[${fieldxpath}]])[1]
    \    ${status}    ${value}=    Run Keyword And Ignore Error    Page Should Contain Element    xpath=${checkxpath}

         # In case the field is not there, log a error
    \    Run Keyword Unless     '${status}' == 'PASS'    Log    Field ${fieldname} not in the view or unvisible
         # In case the field is there, add the path to the xpath
    \    ${xpath}=    Set Variable If    '${status}' == 'PASS'    ${xpath} and descendant::td[${fieldxpath} and string()='${fieldvalue}']    ${xpath}

    # remove first " and " again (5 characters)
    ${xpath}=   Get Substring    ${xpath}    5
    ${xpath}=    Catenate    (//table[contains(@class,'oe_list_content')]//tr[${xpath}]/td)[1]
    Click Element    xpath=${xpath}
    ElementPostCheck

##########  NEW ONES ##########

RadioEnhanced  [Arguments]     ${model}    ${field}

    Wait Until Element Is Visible   jquery:div[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}'] input:last
    Execute Javascript              $("div[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}'] input:last").click()
    Execute Javascript              $("div[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}'] input:last").click()

Float req	[Arguments]	${model}	${field}	${value}
	SelectNotebook	xpath=//div[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']/input
	Modal	Input Text	xpath=//div[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']/input	  value=${value}
	ElementPostCheck

SubMenu2    [Arguments]    ${menu}    ${menu-pos}=0    ${menu-2}=0    ${menu-2-pos}=0    ${menu-3}=0    ${menu-3-pos}=0     ${check}=1
    Wait Until Element Is Visible       jquery:div.oe_secondary_menus_container div.oe_secondary_menu:visible ul li:contains('${menu}'):nth(${menu-pos}) ul li a:contains('${menu-2}'):nth(${menu-2-pos})    ${SELENIUM_TIMEOUT}
    Click Link                          jquery:div.oe_secondary_menus_container div.oe_secondary_menu:visible ul li:contains('${menu}'):nth(${menu-pos}) ul li a:contains('${menu-2}'):nth(${menu-2-pos})
    Run Keyword If                     '${check}' == '1'       Wait Until Page Contains Element    jquery:div.oe_view_manager_current
    ElementPostCheck
    Run Keyword If                      '${menu-3}' != '0'    SubMenu3    ${menu}    ${menu-pos}    ${menu-2}    ${menu-2-pos}    ${menu-3}    ${menu-3-pos}       ${check}

SubMenu3    [Arguments]    ${menu}    ${menu-pos}=0    ${menu-2}=0    ${menu-2-pos}=0    ${menu-3}=0    ${menu-3-pos}=0     ${check}=1
    Wait Until Element Is Visible       jquery:div.oe_secondary_menus_container div.oe_secondary_menu:visible ul li:contains('${menu}'):nth(${menu-pos}) ul li:contains('${menu-2}'):nth(${menu-2-pos}) ul li a:contains('${menu-3}'):nth(${menu-3-pos})    ${SELENIUM_TIMEOUT}
    Click Link                          jquery:div.oe_secondary_menus_container div.oe_secondary_menu:visible ul li:contains('${menu}'):nth(${menu-pos}) ul li:contains('${menu-2}'):nth(${menu-2-pos}) ul li a:contains('${menu-3}'):nth(${menu-3-pos})
    Run Keyword If                     '${check}' == '1'       Wait Until Page Contains Element    jquery:div.oe_view_manager_current
    ElementPostCheck

ElementPreCheck    [Arguments]    ${element}
	Execute Javascript      console.log("${element}");
	# Element may be in a tab. So click the parent tab. If there is no parent tab, forget about the result
    Execute Javascript      var path="${element}".replace('xpath=','');var id=document.evaluate("("+path+")/ancestor::div[contains(@class,'oe_notebook_page')]/@id",document,null,XPathResult.STRING_TYPE,null).stringValue; if(id != ''){ window.location = "#"+id; $("a[href='#"+id+"']").click(); console.log("Clicked at #" + id); } return true;

Button Smart    [Arguments]     ${name}
    Wait Until Page Contains Element	xpath=//div[contains(@class,'o_cp_pager')]
    Wait Until Page Contains Element        xpath=//button/div[contains(@name,'${name}')]
    Run Keyword Unless      '${name}' == ''    Modal    Set Focus To Element    xpath=//div[contains(@name,'${name}')]
    Run Keyword Unless      '${name}' == ''    Modal    Click Element           xpath=//div[contains(@name,'${name}')]
    ElementPostCheck

Many2OneSelectNotFound    [Arguments]    ${model}    ${field}    ${value}
    ElementPreCheck                     xpath=(//div[contains(@class,'openerp')])[last()]//input[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']
    Wait Until Page Contains Element    jquery:div.o_view_manager_content div[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}'] input
    Input Text                          jquery:div.o_view_manager_content div[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}'] input    ${value}
    Wait Until Page Contains Element    jquery:ul.ui-autocomplete:visible li.o_m2o_dropdown_option
    Wait For Condition                  return $('ul.ui-autocomplete:visible li.ui-menu-item:not(".o_m2o_dropdown_option"):first a').text().trim() != '${value}';

Many2OneCreateDirectly    [Arguments]    ${model}    ${field}    ${value}
    Input Text                          jquery:div.openerp:last input[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}']    ${value}
    Wait Until Page Contains Element    jquery:ul.ui-autocomplete:visible li:eq(0) a:contains('Lege "${value}" an')
    Click Link                          jquery:ul.ui-autocomplete:visible li:eq(0) a:contains('Lege "${value}" an')
    Textfield Should Contain            xpath=(//div[contains(@class,'openerp')])[last()]//input[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']    ${value}
    ElementPostCheck

Many2OneCreateAndEdit    [Arguments]    ${model}    ${field}    ${value}    ${li}=0
    ElementPreCheck	    xpath=//div[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']//input
    Input Text		    xpath=//div[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']//input     ${value}
    Wait Until Page Contains Element    jquery:ul.ui-autocomplete:visible li:eq(${li}) a:contains('Anlegen und Bearbeiten')
    Click Link                          jquery:ul.ui-autocomplete:visible li:eq(${li}) a:contains('Anlegen und Bearbeiten')
    ElementPostCheck

Many2OneOpen    [Arguments]    ${model}    ${field}
    Click Element          xpath=(//div[contains(@class,'openerp')])[last()]//span[descendant::input[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']]/i
    ElementPostCheck

ClearMany2OneSelect    [Arguments]    ${model}    ${field}
#    ElementPreCheck         jquery:div.o_field_widget[data-bt-testing-model_name='${model}'][name='${field}'] input
    Execute Javascript      $("div.o_field_widget[data-bt-testing-model_name='${model}'][name='${field}'] input").val('').keyup()
    ElementPostCheck

DatePicker    [Arguments]    ${model}    ${field}
    Click Element                         jquery:div.openerp:last input[data-bt-testing-name='${field}'][data-bt-testing-model_name='${model}'] + .datepickerbutton
    Wait Until Element Is Visible         jquery:.datepicker:visible
    Click Element                         jquery:div.openerp:last input[data-bt-testing-name='${field}'][data-bt-testing-model_name='${model}']
    Wait Until Element Is Not Visible     jquery:.datepicker:visible
    ElementPostCheck

Checkbox    [Arguments]    ${model}    ${field}
    ElementPreCheck        xpath=//div[@data-bt-testing-name='${field}' and @data-bt-testing-model_name='${model}']//input[@type='checkbox']
    Checkbox Should Not Be Selected	xpath=//div[@data-bt-testing-name='${field}' and @data-bt-testing-model_name='${model}']//input[@type='checkbox']
    Click Element          xpath=//div[@data-bt-testing-name='${field}' and @data-bt-testing-model_name='${model}']//input[@type='checkbox']
    ElementPostCheck

NotCheckbox    [Arguments]    ${model}    ${field}
    ElementPreCheck        xpath=//div[@data-bt-testing-name='${field}' and @data-bt-testing-model_name='${model}']//input[@type='checkbox']
    Checkbox Should Be Selected	xpath=//div[@data-bt-testing-name='${field}' and @data-bt-testing-model_name='${model}']//input[@type='checkbox']
    Click Element          xpath=//div[@data-bt-testing-name='${field}' and @data-bt-testing-model_name='${model}']//input[@type='checkbox']
    ElementPostCheck

DeleteOne2Many11    [Arguments]    ${model}    ${field}    ${position}
    ${selector}=                        Set Variable    div[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}'] tbody tr:nth(${position}) td.o_list_record_delete
    Wait Until Page Contains Element    jquery:${selector}
    Click Element                       jquery:${selector}
    ElementPostCheck

SelectOne2Many11    [Arguments]    ${model}    ${field}    ${position}
    ${selector}=                        Set Variable    div[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}'] tbody tr:nth(${position}) td:first
    Wait Until Page Contains Element    jquery:${selector}
    Click Element                       jquery:${selector}
    ElementPostCheck

NewOne2ManyKanban   [Arguments]    ${model}    ${field}
    ElementPreCheck        xpath=(//div[contains(@class,'openerp')])[last()]//div[contains(@class,'oe_form_field_one2many')]//div[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']//button[@data-bt-testing-button='oe_kanban_button_new']
    Click Button           xpath=(//div[contains(@class,'openerp')])[last()]//div[contains(@class,'oe_form_field_one2many')]//div[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']//button[@data-bt-testing-button='oe_kanban_button_new']
    ElementPostCheck

OpenListViewElement   [Arguments]    ${model}    ${value}
    Click Element    xpath=(//div[contains(@class,'o_content')])//table[contains(@class,'o_list_view')]//tr[@data-bt-testing-model_name='${model}']//td[contains(text(), '${value}')]
    ElementPostCheck

KanbanButton                      [Arguments]     ${model}    ${button_name}
    Wait Until Page Contains Element    xpath=//div[contains(@class, 'o_cp_buttons')]//button[contains(@class, '${button_name}')]
    Wait Until Element Is Visible       xpath=//div[contains(@class, 'o_cp_buttons')]//button[contains(@class, '${button_name}')]    ${SELENIUM_TIMEOUT}
    Click Button                        xpath=//div[contains(@class, 'o_cp_buttons')]//button[contains(@class, '${button_name}')]
    Wait For Condition                  return true;    20.0
    ElementPostCheck

Many2ManySelect    [Arguments]    ${model}    ${field}    ${value}
    Input Text      jquery:div[data-bt-testing-name='${field}'] input       ${value}
	Click Element	xpath=//ul[contains(@class,'ui-autocomplete') and not(contains(@style,'display: none'))]/li[1]/a
	ElementPostCheck

Many2ManySelect2    [Arguments]    ${model}    ${field}    ${value}
    Click Element                    jquery:div.o_field_many2one[name='${field}'] input
    Input Text                       jquery:div.o_field_many2one[name='${field}'] input     ${value}
    Wait Until Element Is Visible    jquery:.ui-autocomplete a:contains('${value}')
    Click Element                    jquery:.ui-autocomplete a:contains('${value}')
    Wait Until Element Is Visible    jquery:div.o_field_widget[data-bt-testing-name='${field}'] span.o_badge_text:contains('${value}')

Many2ManyRemove    [Arguments]    ${model}    ${field}    ${value}
    ElementPreCheck    xpath=//div[@data-bt-testing-name='${field}']
    Click Element      xpath=//div[@data-bt-testing-name='${field}']//span[contains(@class, 'badge')][descendant::span[contains(@title, '${value}')]]//span[contains(@class, 'o_delete')]

CalendarViewSelectRecord    [Arguments]    ${model}    ${field}    ${value}
    ElementPostCheck
    Wait Until Page Contains Element   jquery:div.o_view_manager_content:visible div.o_field_${field}:contains('${value}')
    Click Element                      jquery:div.o_view_manager_content:visible div.o_field_${field}:contains('${value}')
    ElementPostCheck

TreeViewSelectRecord    [Arguments]   ${model}     ${value}
    ElementPostCheck
    Wait Until Page Contains Element   jquery:.o_list_table tr[data-bt-testing-model_name='${model}'] td:contains('${value}')
    Click Element                      jquery:.o_list_table tr[data-bt-testing-model_name='${model}'] td:contains('${value}'):eq(0)
    ElementPostCheck

TreeViewSelectRecordByColumn    [Arguments]   ${column}    ${value}
    ElementPostCheck
    ${col_index}=       Execute Javascript      return $("table.o_list_view thead tr").find("th:contains('${column}')").index();
    ${col_index_fix}=   Evaluate    ${col_index} + 1
    Click Element       jquery:tbody tr.o_data_row td.o_data_cell:nth-child(${col_index_fix}):contains('${value}')
    ElementPostCheck

TreeViewSelectRecordByColumnDataName    [Arguments]   ${column_data_name}    ${value}
    ElementPostCheck
    ${col_index}=       Execute Javascript      return $("table.o_list_table thead tr").find("th[data-name=${column_data_name}]").index();
    ${col_index_fix}=   Evaluate    ${col_index} + 1
    Click Element       jquery:tbody tr.o_data_row td.o_data_cell:nth-child(${col_index_fix}):contains('${value}')
    ElementPostCheck

TreeViewSelectCheckbox    [Arguments]   ${model}    ${value}
    ElementPostCheck
    Wait Until Page Contains Element   jquery:div.table-responsive table.o_list_table.table.table-striped tbody tr[data-bt-testing-model_name='${model}'] td:contains('${value}')
    Click Element                      jquery:div.table-responsive table.o_list_table.table.table-striped tbody tr[data-bt-testing-model_name='${model}']:contains('${value}') td.o_list_record_selector
    ElementPostCheck

TreeViewShouldContain    [Arguments]    ${model}    ${value}
    Wait Until Page Contains Element    jquery:div.o_view_manager_content:visible table.o_list_view tr[data-bt-testing-model_name='${model}'] td:contains('${value}')

ListViewButton    [Arguments]    ${model}    ${action}
    Click Button    xpath=(//div[contains(@class,'openerp')])[last()]//td[@data-bt-testing-model_name='${model}' and @data-field='${action}']/button

Editable-Select-Option    [Arguments]    ${model}    ${field}    ${value}
    ElementPreCheck             xpath=(//div[contains(@class,'o_main_content')])[last()]//div//select[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']
    Click Element               xpath=(//div[contains(@class,'o_main_content')])[last()]//div//select[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']
    Select From List By Label	xpath=(//div[contains(@class,'o_main_content')])[last()]//div//select[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']    ${value}
    ElementPostCheck

Modal-Select-Option    [Arguments]    ${model}    ${field}    ${value}
    ElementPreCheck                  xpath=//div[contains(@class, 'modal-body')]//select[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']
    Wait Until Element Is Visible    xpath=//div[contains(@class, 'modal-body')]//select[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']
    Click Element                    xpath=//div[contains(@class, 'modal-body')]//select[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']
    Select From List By Label        xpath=//div[contains(@class, 'modal-body')]//select[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']    ${value}
    ElementPostCheck

Editable-Char    [Arguments]    ${model}    ${field}    ${value}
    ElementPreCheck        xpath=(//div[contains(@class,'o_main_content')])//input[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']
    Execute Javascript     $("div.o_main_content:last input[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}']").val(''); return true;
    Input Text             xpath=(//div[contains(@class,'o_main_content')])//input[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']    ${value}
    ElementPostCheck

Modal-Editable-Char    [Arguments]    ${model}    ${field}    ${value}
    ElementPreCheck        xpath=//div[contains(@class, 'modal-body')]//input[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']
    Execute Javascript     $("div.modal-body:last input[data-bt-testing-model_name='${model}'][data-bt-testing-name='${field}']").val(''); return true;
    Input Text             xpath=(//div[contains(@class,'modal-body')])//input[@data-bt-testing-model_name='${model}' and @data-bt-testing-name='${field}']    ${value}
    ElementPostCheck

Logout
    Click Link    xpath=//div[@id='oe_main_menu_placeholder']/ul[contains(@class, 'oe_user_menu_placeholder')]/li/a
    Click Link    xpath=//div[@id='oe_main_menu_placeholder']/ul[contains(@class, 'oe_user_menu_placeholder')]/li/ul/li/a[contains(@data-menu, 'logout')]
    Wait Until Page Contains Element    name=login

SearchField
    [Arguments]    ${field}    ${value}
    [Documentation]     Use the search in list views.
    ...                 'field': Name of the field to filter
    ...                 'value': Value to use in the filter
    Wait Until Element Is Visible   jquery:div.o_cp_searchview div.o_searchview input.o_searchview_input
    Input Text                      jquery:div.o_cp_searchview div.o_searchview input.o_searchview_input        ${value}
    Wait Until Element Is Visible   jquery:div.o_searchview_autocomplete li a em:contains('${field}')
    Click Element                   jquery:div.o_searchview_autocomplete li a em:contains('${field}')
    ElementPostCheck

ClearFilter
    sleep       2
    ${selector}=       Set Variable    div.o_searchview div.o_searchview_facet div.o_facet_remove:visible
    ${filters}=        Execute Javascript    return $("${selector}").toArray();
    FOR    ${f}     IN      @{filters}
        Click Element    jquery:${selector}
    END
    Wait Until Page Does Not Contain Element  jquery:${selector}    5
    ElementPostCheck

FormShouldContain    [Arguments]     ${label}      ${value}
    Wait Until Page Contains Element         jquery:td.o_td_label:contains('${label}'):visible + td:contains('${value}')

SidebarAction    [Arguments]	${action_text}    ${menu_text}=    ${index}=
    Click Element    xpath=//div[contains(@class,'o_cp_sidebar')]/div[contains(@class,'btn-group')]/div[contains(@class,'o_dropdown')]/button[contains(text(), '${action_text}')]
    Run Keyword Unless      '${menu_text}' == ''    Click Element    xpath=//div[contains(@class,'o_cp_sidebar')]/div[contains(@class,'btn-group')]/div[contains(@class,'o_dropdown')]/ul[contains(@class,'dropdown-menu')]/li/a[contains(text(),'${menu_text}')]
    # index not migrated to 11 yet
    Run Keyword Unless      '${index}' == ''        Click Element    xpath=//div[contains(@class,'o_cp_sidebar')]/div[contains(@class,'btn-group')]/div[contains(@class,'o_dropdown')]/button/span[contains(text(), '${action_text}')]/../../div[contains(@class,'dropdown-menu')]/a[contains(@data-index,'${index}')]
    ElementPostCheck