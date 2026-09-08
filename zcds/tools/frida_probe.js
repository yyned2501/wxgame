// dump.js - 尝试找占城大师 session token
console.log('[*] attach ok, pid=' + Process.id);
console.log('[*] enumerating modules...');
var mods = Process.enumerateModules();
console.log('[*] total modules: ' + mods.length);
mods.slice(0, 10).forEach(function(m) {
    console.log('  ' + m.name + ' @ ' + m.base.toString() + ' size=' + m.size);
});

// 找主模块名
var main = mods[0];
console.log('[*] main module: ' + main.name);

// 看主模块 exports 数量
console.log('[*] enumerating exports of main module...');
try {
    var exps = main.enumerateExports();
    console.log('[*] exports count: ' + exps.length);
    exps.slice(0, 5).forEach(function(e) {
        console.log('  ' + e.name + ' @ ' + e.address.toString());
    });
} catch (e) {
    console.log('  ERROR: ' + e.message);
}

// 找含 wx 或 game 字符串的内存地址
console.log('[*] scanning memory for game markers...');
var markers = ['wx9eed71970378b2ae', 'cszdz-cn-wx', 'Base64KeyStr', 'XyxLogin'];
markers.forEach(function(m) {
    var found = Memory.scanSync(Process.findModuleByName('WeChatAppEx.exe').base, Process.findModuleByName('WeChatAppEx.exe').size, m);
    console.log('  ' + m + ': ' + found.length + ' hits');
    if (found.length > 0) {
        found.slice(0, 3).forEach(function(f) {
            console.log('    @' + f.address.toString() + ' context: ' + hexdump(f.address, {length: 32}));
        });
    }
});
console.log('[*] done');
