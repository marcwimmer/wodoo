
/**
 * Generated using theia-plugin-generator
 */

import * as theia from '@theia/plugin';
//import { inject, injectable, named, postConstruct } from 'inversify';
//import { ILogger } from '@theia/core/lib/common';
//import * as ttask from '@theia/core';



// const buildSteps: theia.TaskConfigurations[] = [
//     {
//         "_scope": theia.TaskScope.Global,
//         "label": "Run Echo",
//         "type": "shell",
//         "command": "/usr/bin/echo",
//         "args": [
//             "hello"
//         ],
//         "options": {
//             "cwd": "/opt/odoo"
//         }
//     }
// ];

export function start(context: theia.PluginContext) {
    const informationMessageTestCommand = {
        id: 'hello-world-example-generated',
        label: "Hello World"
    };
    context.subscriptions.push(theia.commands.registerCommand(informationMessageTestCommand, (...args: any[]) => {
        theia.window.showInformationMessage('Hello Backend!');


    }));

}

export function stop() {

}
