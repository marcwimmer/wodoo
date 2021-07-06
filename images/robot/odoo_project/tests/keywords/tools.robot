*** Settings ***
Documentation                Some Tools
Library                      ../library/odoo.py
Library                      Collections


*** Keywords ***

Set Dict Key    [Arguments]
				...          ${data}
				...          ${key}
				...          ${value}
    tools.Set Dict Key        ${data}  ${key}  ${value}

Get Now As String       [Arguments]
                        ...           ${dummy}=${FALSE}
	${result}=    tools.Get Now
	${result}=    Set Variable          ${result.strftime("%Y-%m-%d %H:%M:%S")}
	[return]      ${result}

Get Guid        [Arguments]
                ...           ${dummy}=${FALSE}
	${result}=    tools.Get Guid
	[return]      ${result}