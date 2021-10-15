# Find out compatible typescript version
npm dist-tags @types/assert

Typescript 3.5.3 is being used.  And node 12 by theia.

So in the yo generated plugin add at devDependencies:
{"devDependencies": "@types/node": "12.12.6" }
This is also written after the make-plugin.sh command is executed. 


Steps:
1. theia-make-plugin-generator/make-plugin.sh
2. cd to plugin then:
   npm install  (to update the @types/node which raises error otherwise)
   yarn build (inside started theia container)