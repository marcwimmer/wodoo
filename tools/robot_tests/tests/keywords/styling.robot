*** Keywords ***
Highlight heading
    [Arguments]  ${locator}
    Update element style  ${locator}  border  2px solid red
    Highlight  ${locator}

Highlight Fancy
    [Arguments]  ${fancylocator}
    Update element style  ${fancylocator}  box-shadow  0 0 0 999999px rgba(0,0,0,.8)

Show Number
    [Arguments]  ${locator}  ${text}
    Add Dot 
    ...    ${locator}
    ...    left=-8
    ...    text=${text}

Red Rect on
    [Arguments]  ${locator}
    Update Element Style    
    ...    ${locator}
    ...    outline
    ...    solid red 3px

Annotate
    [Arguments]  ${locator}  ${note}
    Add pointy note
    ...  ${locator}
    ...  text=${note}
    ...  position=right