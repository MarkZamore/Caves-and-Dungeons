recipes.remove(<item:explorerscompass:explorerscompass>);
recipes.remove(<item:naturescompass:naturescompass>);
recipes.remove(<item:just_in_cave:iron_hammer>);
recipes.remove(<item:just_in_cave:gold_hammer>);
recipes.remove(<item:just_in_cave:stone_hammer>);
recipes.remove(<item:just_in_cave:copper_sword>);
recipes.remove(<item:just_in_cave:copper_shovel>);
recipes.remove(<item:just_in_cave:copper_axe>);
recipes.remove(<item:just_in_cave:copper_hoe>);
recipes.remove(<item:just_in_cave:rose_gold_hammer>);
recipes.remove(<item:just_in_cave:wooden_hammer>);
recipes.remove(<item:just_in_cave:copper_chestplate>);
recipes.remove(<item:just_in_cave:copper_helmet>);
recipes.remove(<item:just_in_cave:copper_pickaxe>);
recipes.remove(<item:just_in_cave:netherite_hammer>);
recipes.remove(<item:just_in_cave:diamond_hammer>);
recipes.remove(<item:just_in_cave:copper_leggings>);
recipes.remove(<item:just_in_cave:copper_boots>);
recipes.remove(<item:just_in_cave:steel_shovel>);
recipes.remove(<item:just_in_cave:steel_sword>);
recipes.remove(<item:just_in_cave:steel_hoe>);
recipes.remove(<item:just_in_cave:steel_axe>);
recipes.remove(<item:just_in_cave:steel_pickaxe>);
recipes.remove(<item:just_in_cave:golden_stick>);
recipes.remove(<item:just_in_cave:iron_stick>);
recipes.remove(<item:just_in_cave:rose_gold_ingot>);
craftingTable.addShaped("naturescompass", <item:naturescompass:naturescompass>, [
    [<tag:items:minecraft:planks>,  <item:minecraft:compass>, <tag:items:minecraft:planks>],
    [<item:galosphere:barometer>, <item:cavesanddepths:rose_gold_ingot>, <item:spelunkery:depth_gauge>],
    [<tag:items:minecraft:planks>, <item:minecraft:clock>, <tag:items:minecraft:planks>]
]);
craftingTable.addShaped("explorerscompass", <item:explorerscompass:explorerscompass>, [
    [<item:quark:chiseled_tuff_bricks>,  <item:galosphere:silver_ingot>, <item:quark:chiseled_tuff_bricks>],
    [<item:minecraft:recovery_compass>, <item:naturescompass:naturescompass>, <item:spelunkery:magnetic_compass>],
    [<item:quark:chiseled_tuff_bricks>, <item:waystones:warp_dust>, <item:quark:chiseled_tuff_bricks>]
]);
craftingTable.addShaped("night_vision_goggles", <item:artifacts:night_vision_goggles>, [
    [<item:minecraft:lead>,  <item:lampcrafting:light_reflector>, <item:minecraft:lead>],
    [<item:spelunkery:rough_emerald>, <item:spelunkery:nephrite_charm>, <item:spelunkery:rough_emerald>],
    [<item:cavesanddepths:glittering_dust>, <item:minecraft:air>, <item:cavesanddepths:glittering_dust>]
]);
craftingTable.addShaped("diggers_power", <item:mods_for_caves:diggers_power>, [
    [<item:cavesanddepths:rose_gold_ingot>,  <item:minecraft:golden_pickaxe>, <item:cavesanddepths:rose_gold_ingot>],
    [<item:galosphere:silver_ingot>, <item:spelunkery:cinnabar_block>, <item:galosphere:silver_ingot>],
    [<item:cavesanddepths:rose_gold_ingot>, <item:minecraft:magma_cream>, <item:cavesanddepths:rose_gold_ingot>]
]);
craftingTable.addShapeless("glowstonedust", <item:minecraft:glowstone_dust>, [<item:minecraft:sand>, <item:cavesanddepths:glittering_dust>]);
craftingTable.addShapeless("glitteringdust6", <item:cavesanddepths:glittering_dust> * 6, [<item:alexscaves:bioluminesscence>]);
craftingTable.addShapeless("glitteringdust31", <item:cavesanddepths:glittering_dust> * 3, [<item:spelunkery:mushgloom>]);
craftingTable.addShapeless("glitteringdust32", <item:cavesanddepths:glittering_dust> * 3, [<item:sculks_of_arda:sculk_fungus>]);
craftingTable.addShapeless("glitteringdust21", <item:cavesanddepths:glittering_dust> * 2, [<item:spelunkery:phosphor_fungus>]);
craftingTable.addShapeless("glitteringdust22", <item:cavesanddepths:glittering_dust> * 2, [<item:quark:glow_shroom>]);
craftingTable.addShapeless("glitteringdust62", <item:cavesanddepths:glittering_dust> * 6, [<item:illuminative:glow_fish_item>]);
craftingTable.addShapeless("blazepowder", <item:minecraft:blaze_powder>, [<item:alexscaves:sulfur_dust>, <item:minecraft:glowstone_dust>]);
craftingTable.addShapeless("blazerod", <item:minecraft:blaze_rod> * 3, [<item:alexscaves:ambersol>]);
craftingTable.addShapeless("pink_salt_straw", <item:galosphere:pink_salt_straw>, [<item:spelunkery:rock_salt>]);
craftingTable.addShapeless("rock_salt", <item:spelunkery:rock_salt>, [<item:galosphere:pink_salt_straw>]);
craftingTable.addShapeless("rose_gold", <item:cavesanddepths:rose_gold_ingot>, [<item:just_in_cave:granite>, <tag:items:forge:ingots/gold>]);

