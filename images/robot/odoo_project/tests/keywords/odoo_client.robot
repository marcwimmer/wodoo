*** Settings ***
Documentation                Interface to odoo-rpclib
Resource                     ../keywords/odoo_client.robot
Library                      ../library/odoo.py
Library                      Collections


*** Keywords ***

Technical Testname            [Arguments]  ${testname}
    ${result}=                odoo.Technical Testname  ${testname}
    [return]                  ${result}


Odoo Conn                     [Arguments]
                              ...                           ${dbname}=${ODOO_DB}
                              ...                           ${host}=${ODOO_URL}
                              ...                           ${user}=${ODOO_USER}
                              ...                           ${pwd}=${ODOO_PASSWORD}
    ${conn}=                  odoo._get Conn  ${host}  ${dbname}  ${user}  ${pwd}
    [return]                  ${conn}

Odoo Search   [Arguments]
              ...             ${model}
              ...             ${domain}
              ...             ${dbname}=${ODOO_DB}
              ...             ${host}=${ODOO_URL}
              ...             ${user}=${ODOO_USER}
              ...             ${pwd}=${ODOO_PASSWORD}
              ...             ${count}=${FALSE}
              ...             ${limit}=${NONE}
              ...             ${order}=${NONE}
              ...             ${lang}=en_US
              ...             ${context}=${NONE}
    ${result}=  odoo.Rpc Client Search    ${host}  ${dbname}  ${user}  ${pwd}  ${model}  ${domain}  ${limit}  ${order}  ${count}  lang=${lang}  context=${context}
    [return]                  ${result}

Odoo Search Read    [Arguments]
                    ...             ${model}
                    ...             ${domain}
                    ...             ${fields}
                    ...             ${dbname}=${ODOO_DB}
                    ...             ${host}=${ODOO_URL}
                    ...             ${user}=${ODOO_USER}
                    ...             ${pwd}=${ODOO_PASSWORD}
                    ...             ${count}=${FALSE}
                    ...             ${limit}=${NONE}
                    ...             ${order}=${NONE}
                    ...             ${lang}=en_US
                    ...             ${context}=${NONE}
    ${ids}=  odoo.Rpc Client Search    ${host}  ${dbname}  ${user}  ${pwd}  ${model}  ${domain}  ${limit}  ${order}  ${count}  lang=${lang}  context=${context}
    ${result}=  odoo.Rpc Client Read   ${host}  ${dbname}  ${user}  ${pwd}  ${model}  ${ids}  ${fields} 
    [return]                  ${result}


Odoo Search Records  [Arguments]
...                           ${model}
...                           ${domain}
...                           ${dbname}=${ODOO_DB}
...                           ${host}=${ODOO_URL}
...                           ${user}=${ODOO_USER}
...                           ${pwd}=${ODOO_PASSWORD}
...                           ${count}=${FALSE}
...                           ${limit}=${NONE}
...                           ${order}=${NONE}
                     ...      ${lang}=en_US
                     ...      ${context}=${None}
    Log To Console            ${lang}
    Log To Console            ${context}
    ${result}=  odoo.Rpc Client Search Records   ${host}  ${dbname}  ${user}  ${pwd}  ${model}  ${domain}  ${limit}  ${order}  ${count}  lang=${lang}  context=${context}
    [return]                  ${result}

Odoo Load Data   [Arguments]
                 ...          ${filepath}
                 ...          ${module_name}
                 ...          ${dbname}=${ODOO_DB}
                 ...          ${host}=${ODOO_URL}
                 ...          ${user}=${ODOO_USER}
                 ...          ${pwd}=${ODOO_PASSWORD}
    odoo.Load File            ${host}  ${dbname}  ${user}  ${pwd}  ${CURDIR}/../${filepath}  ${module_name}  ${TEST NAME}

Odoo Get Latest File In Folder      [Arguments]
                                    ...      ${parent_folder}
                                    ...      ${glob}=**/*
                                    ...      ${younger_than}=${{1980-04-04}}
                                    ...      ${wait_until_exists}=0
                                    ...      ${dbname}=${ODOO_DB}
                                    ...      ${host}=${ODOO_URL}
                                    ...      ${user}=${ODOO_USER}
                                    ...      ${pwd}=${ODOO_PASSWORD}
    ${result}=                      odoo.Get Latest File In Folder    ${host}  ${dbname}  ${user}  ${pwd}  ${parent_folder}  ${glob}  ${younger_than}  ${wait_until_exists}
    [return]                        ${result}

Odoo Put File        [Arguments]
                     ...      ${file_path}
                     ...      ${dest_path_on_odoo_container}
                     ...      ${dbname}=${ODOO_DB}
                     ...      ${host}=${ODOO_URL}
                     ...      ${user}=${ODOO_USER}
                     ...      ${pwd}=${ODOO_PASSWORD}
    odoo.Put File            ${host}  ${dbname}  ${user}  ${pwd}  ${CURDIR}/../${file_path}  ${dest_path_on_odoo_container} 

Odoo Put Dict As File       [Arguments]
                             ...      ${data}
                             ...      ${dest_path_on_odoo_container}
                             ...      ${dbname}=${ODOO_DB}
                             ...      ${host}=${ODOO_URL}
                             ...      ${user}=${ODOO_USER}
                             ...      ${pwd}=${ODOO_PASSWORD}
    odoo.Put Dict Content as File           ${host}  ${dbname}  ${user}  ${pwd}  ${data}  ${dest_path_on_odoo_container} 

Odoo Create   [Arguments]
              ...             ${model}
              ...             ${values}
              ...             ${dbname}=${ODOO_DB}
              ...             ${host}=${ODOO_URL}
              ...             ${user}=${ODOO_USER}
              ...             ${pwd}=${ODOO_PASSWORD}
              ...             ${lang}=en_US
              ...             ${context}=${None}
    ${new_dict}=    Convert To Dictionary    ${values}
    Log to Console    Create new ${model} with dict: ${new_dict}
    ${result}=  odoo.Rpc Client Create    ${host}  ${dbname}  ${user}  ${pwd}  ${model}  ${new_dict}  lang=${lang}  context=${context}
    [return]                  ${result}

Odoo Write  [Arguments]
            ...              ${model}
            ...              ${ids}
            ...              ${values}
            ...              ${dbname}=${ODOO_DB}
            ...              ${host}=${ODOO_URL}
            ...              ${user}=${ODOO_USER}
            ...              ${pwd}=${ODOO_PASSWORD}
            ...              ${lang}=en_US
            ...              ${context}=${None}
    ${values}=               Convert To Dictionary    ${values}
    Log to Console           Write ${ids} ${model} with dict: ${values}
    ${result}=               odoo.Rpc Client Write    host=${host}  dbname=${dbname}  user=${user}  pwd=${pwd}  model=${model}  ids=${ids}  values=${values}  lang=${lang}  context=${context}
    [return]                 ${result}

Odoo Unlink  [Arguments]
            ...              ${model}
            ...              ${ids}
            ...              ${dbname}=${ODOO_DB}
            ...              ${host}=${ODOO_URL}
            ...              ${user}=${ODOO_USER}
            ...              ${pwd}=${ODOO_PASSWORD}
            ...              ${context}=${None}
    ${result}=               odoo.Rpc Client Execute    method=unlink  host=${host}  dbname=${dbname}  user=${user}  pwd=${pwd}  model=${model}  ids=${ids}  context=${context}
    [return]                 ${result}

Odoo Search Unlink  [Arguments]
            ...              ${model}
            ...              ${domain}
            ...              ${dbname}=${ODOO_DB}
            ...              ${host}=${ODOO_URL}
            ...              ${user}=${ODOO_USER}
            ...              ${pwd}=${ODOO_PASSWORD}
            ...              ${lang}=en_US
            ...              ${context}=${None}
            ...              ${limit}=${None}
            ...              ${order}=${None}
    ${ids}=                  odoo.Rpc Client Search    ${host}  ${dbname}  ${user}  ${pwd}  ${model}  ${domain}  ${limit}  ${order}  lang=${lang}  context=${context}
    Set Global Variable      ${result}  ${None}
    IF                       ${ids}
    ${result}=               odoo.Rpc Client Execute    method=unlink  host=${host}  dbname=${dbname}  user=${user}  pwd=${pwd}  model=${model}  ids=${ids}  lang=${lang}  context=${context}
    END

    Log To Console           Nach Aufruf unlink: ${result}

    [return]                 ${True}

Odoo Ref Id   [Arguments]
               ...            ${xml_id}
               ...            ${dbname}=${ODOO_DB}
               ...            ${host}=${ODOO_URL}
               ...            ${user}=${ODOO_USER}
               ...            ${pwd}=${ODOO_PASSWORD}
    Log to Console    XML ID: ${xml_id}
    ${result}=  odoo.Rpc Client Ref Id    ${host}  ${dbname}  ${user}  ${pwd}  ${xml_id}
    [return]                  ${result}

Odoo Ref   [Arguments]
           ...                ${xml_id}
           ...                ${dbname}=${ODOO_DB}
           ...                ${host}=${ODOO_URL}
           ...                ${user}=${ODOO_USER}
           ...                ${pwd}=${ODOO_PASSWORD}
    Log to Console    XML ID: ${xml_id}
    ${result}=  odoo.Rpc Client Ref    ${host}  ${dbname}  ${user}  ${pwd}  ${xml_id}
    [return]                  ${result}

Odoo Execute    [Arguments]
                ...                ${model}
                ...                ${method}
                ...                ${ids}=${FALSE}
                ...                ${params}=[]
                ...                ${kwparams}={}
                ...                ${dbname}=${ODOO_DB}
                ...                ${host}=${ODOO_URL}
                ...                ${user}=${ODOO_USER}
                ...                ${pwd}=${ODOO_PASSWORD}
                ...                ${lang}=en_US
                ...                ${context}=${None}
    ${result}=                     odoo.Rpc Client Execute    ${host}  ${dbname}  ${user}  ${pwd}  ${model}  ${ids}  ${method}  ${params}  ${kwparams}  lang=${lang}  context=${context}
    [return]                       ${result}


Odoo Read    [Arguments]
             ...              ${model}
             ...              ${ids}
             ...              ${fields}
             ...              ${dbname}=${ODOO_DB}
             ...              ${host}=${ODOO_URL}
             ...              ${user}=${ODOO_USER}
             ...              ${pwd}=${ODOO_PASSWORD}
             ...              ${lang}=en_US
             ...              ${context}=${None}
    ${result}=  odoo.Rpc Client Read    ${host}  ${dbname}  ${user}  ${pwd}  ${model}  ${ids}  ${fields}  lang=${lang}  context=${context}
    [return]                  ${result}

Odoo Read Field    [Arguments]
                   ...        ${model}
                   ...        ${id}
                   ...        ${field}
                   ...        ${Many2one}
                   ...        ${dbname}=${ODOO_DB}
                   ...        ${host}=${ODOO_URL}
                   ...        ${user}=${ODOO_USER}
                   ...        ${pwd}=${ODOO_PASSWORD}
                   ...        ${lang}=en_US
                   ...        ${context}=${None}
    ${result}=  odoo.Rpc Client Get Field    ${host}  ${dbname}  ${user}  ${pwd}  ${model}  ${id}  ${field}    ${Many2one}  lang=${lang}  context=${context}
    [return]                  ${result}

Odoo Exec Sql    [Arguments]
                   ...        ${sql}
                   ...        ${dbname}=${ODOO_DB}
                   ...        ${host}=${ODOO_URL}
                   ...        ${user}=${ODOO_USER}
                   ...        ${pwd}=${ODOO_PASSWORD}
    ${result}=  odoo.Exec Sql    ${host}  ${dbname}  ${user}  ${pwd}  ${sql}
    [return]                  ${result}