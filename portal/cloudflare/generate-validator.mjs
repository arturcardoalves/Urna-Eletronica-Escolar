import {readFileSync,writeFileSync,copyFileSync} from 'node:fs';
import Ajv from 'ajv';
import standalone from 'ajv/dist/standalone/index.js';
const ajv=new Ajv({strict:false,allErrors:false,code:{source:true,esm:false}});
const validate=ajv.compile(JSON.parse(readFileSync(new URL('./document-schema.json',import.meta.url),'utf8')));
writeFileSync(new URL('./src/validate.cjs',import.meta.url),'// Generated from document-schema.json by generate-validator.mjs. Do not edit.\n'+standalone(ajv,validate));

// Bundle the pinned decoder locally: no third-party CDN or camera image upload.
copyFileSync(new URL('./node_modules/jsqr/dist/jsQR.js',import.meta.url),new URL('../static/jsQR.js',import.meta.url));
copyFileSync(new URL('./node_modules/jsqr/LICENSE',import.meta.url),new URL('../static/jsQR.LICENSE.txt',import.meta.url));
