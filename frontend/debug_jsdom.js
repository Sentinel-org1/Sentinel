import { JSDOM, VirtualConsole } from 'jsdom';

const virtualConsole = new VirtualConsole();
virtualConsole.on("error", (...args) => console.error("JSDOM Error:", ...args));
virtualConsole.on("log", (...args) => console.log("JSDOM Log:", ...args));
virtualConsole.on("warn", (...args) => console.warn("JSDOM Warn:", ...args));

JSDOM.fromURL("http://localhost:3000", {
  runScripts: "dangerously",
  resources: "usable",
  virtualConsole
}).then(dom => {
  setTimeout(() => {
    console.log("JSDOM HTML:", dom.window.document.body.innerHTML);
    process.exit(0);
  }, 5000);
}).catch(err => {
  console.error(err);
  process.exit(1);
});
