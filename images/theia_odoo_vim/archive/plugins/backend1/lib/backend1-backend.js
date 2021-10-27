"use strict";
/**
 * Generated using theia-plugin-generator
 */
Object.defineProperty(exports, "__esModule", { value: true });
const theia = require("@theia/plugin");
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
function start(context) {
    const informationMessageTestCommand = {
        id: 'hello-world-example-generated',
        label: "Hello World"
    };
    context.subscriptions.push(theia.commands.registerCommand(informationMessageTestCommand, (...args) => {
        theia.window.showInformationMessage('Hello Backend!');
    }));
}
exports.start = start;
function stop() {
}
exports.stop = stop;
//# sourceMappingURL=backend1-backend.js.map