/** Install the `.jsx` compile hook for every test process. */
import { register } from 'node:module';

register('./jsx-hooks.mjs', import.meta.url);
