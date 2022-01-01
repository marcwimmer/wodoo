
/**
 * Generated using theia-plugin-generator
 */

import * as theia from '@theia/plugin';

// import { injectable, inject } from "inversify";
// import { CommandContribution, CommandRegistry, MenuContribution, MenuModelRegistry, MessageService } from "@theia/core/lib/common";
// import { CommonMenus } from "@theia/core/lib/browser";
// import { TaskConfiguration } from '@theia/task/lib/common';
// import { TaskService } from '@theia/task/lib/browser/task-service';

//import * as fs from 'fs'; // In NodeJS: 'const fs = require('fs')'
//import * as path from 'path'; // In NodeJS: 'const fs = require('fs')'
const buildSteps: theia.TaskConfiguration[] = [
    {
        "_scope": theia.TaskScope.Global,
        "label": "Run Echo",
        "type": "shell",
        "command": "/usr/bin/echo",
        "args": [
            "hello"
        ],
        "options": {
            "cwd": "/opt/odoo"
        }
    },
];

export function start(context: theia.PluginContext) {
    const informationMessageTestCommand = {
        id: 'hello-world-example-generated',
        label: "Hello World"
    };
    context.subscriptions.push(theia.commands.registerCommand(informationMessageTestCommand, (...args: any[]) => {
        theia.window.showInformationMessage('Hello World!  4');

        theia.window.showInformationMessage(theia.workspace.name || '');
        theia.window.showInformationMessage(theia.workspace.rootPath || '');
        if (theia.window.activeTextEditor) {
            theia.window.showInformationMessage(theia.window.activeTextEditor.document.uri.path || '');
        }
        //const data = fs.readFileSync("/tmp/a", 'UTF-8').trim();
        //theia.window.showInformationMessage(data);
        const shell = new theia.ShellExecution("rm /tmp/a");
        theia.window.showInformationMessage((shell.command || '').toString());
        theia.tasks.executeTask(buildSteps[0]);

    }));

}

export function stop() {

}
