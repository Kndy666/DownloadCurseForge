from mods.downloadMods import downloadMods
from pack.downloadPack import exportZip

if __name__ == '__main__':
    exportZip("https://www.curseforge.com/minecraft/modpacks/sevtech-ages");
    downloadMods(20);