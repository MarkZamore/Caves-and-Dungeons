"""Build the Russian, reward-free FTB Quests 2001.4 book from actual advancements."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[2]
BOOK = Path("config/ftbquests/quests")
RESOURCES = Path("tools/world-type-lock/src/lock/resources")


def code(value: str) -> str:
    """Positive signed-long IDs remain stable when unrelated quests are added."""
    return f"{int.from_bytes(hashlib.sha256(('cad:quests:' + value).encode()).digest()[:8], 'big') & ((1 << 63) - 1):016X}"


def component(value) -> str:
    # FTB TextUtils.parseRawText accepts Minecraft Component JSON in a string.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def advancements(root: Path) -> dict:
    result = {}
    sources = [root / "minecraft-1.20.1-client.jar", *sorted((root / "mods").glob("*.jar"))]
    for source in sources:
        with zipfile.ZipFile(source) as archive:
            for name in sorted(archive.namelist()):
                parts = name.split("/")
                if len(parts) >= 4 and parts[0] == "data" and parts[2] == "advancements" and name.endswith(".json"):
                    result[parts[1] + ":" + "/".join(parts[3:])[:-5]] = json.loads(archive.read(name))
    # Authored override of the sole literal English display is in the mandatory
    # top-priority server-data pack; read layers in the same order as Minecraft.
    for resources in [root / RESOURCES, root / RESOURCES / "builtin/russian-advancements"]:
        for path in sorted((resources / "data").glob("*/advancements/**/*.json")):
            relative = path.relative_to(resources / "data")
            result[relative.parts[0] + ":" + "/".join(relative.parts[2:])[:-5]] = json.loads(path.read_text(encoding="utf-8"))
    return result


def exclusions(root: Path, all_adv: dict) -> set[str]:
    source = json.loads((root / "tools/quests/runtime-exclusions.json").read_text(encoding="utf-8"))
    for path, expected_hash in source["sourceSha256"].items():
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != expected_hash:
            raise ValueError("Recheck native advancement conditions after changing " + path)
    for key, item in source["advancements"].items():
        if all_adv.get(key, {}).get("conditions") != item["conditions"]:
            raise ValueError("Excluded advancement's native condition changed: " + key)
    return set(source["advancements"])


def native_icon(display: dict) -> object:
    icon = display.get("icon", {})
    if not icon.get("item"):
        return "minecraft:book"
    if "nbt" in icon:
        # NBT-bearing icons can use unsupported or dynamic mod tags. The task
        # itself retains FTB's native icon; the quest uses the plain item.
        return icon["item"]
    return icon["item"]


MOD_NAMES = {
    "alexscaves": "Редкие пещеры: прочие открытия", "alexsmobs": "Животные и чудовища",
    "artifacts": "Артефакты", "botanypots": "Сад в горшках", "bunker_down": "Жизнь в бункере",
    "cavesanddepths": "Розовое золото", "nova_structures": "Подземелья и таверны",
    "dungeons_enhanced": "Большие сооружения", "exposure": "Фотография",
    "friendsandfoes": "Друзья и недруги", "galosphere": "Кристаллы и серебро",
    "glowroot": "Светокорень", "lampcrafting": "Лампы и освещение", "oreganized": "Свинец и электрум",
    "quark": "Маленькие открытия", "repurposed_structures": "Необычные сооружения",
    "resource_ghouls": "Ресурсный гуль", "spelunkery": "Искусство спелеолога",
    "betterdungeons": "Подземелья Юнга", "yungscavebiomes": "Пещерные биомы Юнга",
}
CAVE_NAMES = {
    "discover_magnetic_caves": "Магнитные пещеры", "discover_primordial_caves": "Первобытные пещеры",
    "discover_toxic_caves": "Токсичные пещеры", "discover_abyssal_chasm": "Подводная бездна",
    "discover_forlorn_hollows": "Забвенные пустоты", "discover_candy_cavity": "Конфетный котлован",
}


def mainline() -> list[dict]:
    """Short original guide, inspired by TFCR2's eras, branches and helpful prose."""
    A = "alexscaves:alexscaves/"
    S = "spelunkery:spelunkery/"
    return [
        {"key": "start", "title": "1. Жизнь под землёй", "icon": "minecraft:stone_pickaxe", "quests": [
            {"key": "welcome", "title": "Выход только через Край", "text": [
                "Вы начинаете в подземном бункере. Солнечное излучение делает поверхность опасной, а портал в Незер закрыт. Ваша цель — подготовиться под землёй и добраться до Края.",
                "Как в TerraFirma Rebirth 2, основные главы дают короткий маршрут, а дополнительные посвящены отдельным занятиям. Здесь нет наград: ни предметов, ни опыта, ни команд.",
                "Достижения отмечаются автоматически, в том числе полученные раньше. Галочки нужны только для памяток. Предметные задания проверяют инвентарь и ничего не забирают.",
                "Откройте книгу кнопкой заданий в инвентаре или назначенной в управлении клавишей FTB Quests. Все главы можно читать сразу."
            ], "icon": "minecraft:book"},
            {"adv": "minecraft:story/mine_stone", "after": "welcome", "text": ["Осмотрите бункер и добудьте камень для первых инструментов. Берегите стартовые запасы: снаружи предстоит жить в пещерах."]},
            {"adv": "minecraft:story/upgrade_tools", "after": "minecraft:story/mine_stone", "text": ["Каменная кирка откроет доступ к железной руде. Освещайте путь и отмечайте дорогу обратно."]},
            {"adv": "minecraft:story/smelt_iron", "after": "minecraft:story/upgrade_tools", "text": ["Переплавьте железо. Ведро, щит, кирка и броня полезнее рискованной вылазки на поверхность."]},
            {"adv": "minecraft:story/iron_tools", "after": "minecraft:story/smelt_iron", "text": ["С железной киркой можно заняться самоцветами и более редкими подземными ресурсами."]},
            {"adv": "minecraft:story/obtain_armor", "after": "minecraft:story/smelt_iron", "text": ["Подготовьте железную броню до встречи с обитателями глубоких пещер."]},
            {"adv": "bunker_down:plant_underroot", "after": "welcome", "text": ["Подземный корень из Bunker Down даёт древесину без выхода на поверхность. Посадите его семена и устройте постоянный источник дерева."]},
            {"adv": "bunker_down:cook_underroot", "after": "bunker_down:plant_underroot", "text": ["Часть семян можно приготовить. Сохраните запас для новых посадок."]},
        ]},
        {"key": "equipment", "title": "2. Камни и снаряжение", "icon": "minecraft:diamond_pickaxe", "quests": [
            {"adv": S + "rough_gem", "after": "minecraft:story/iron_tools", "text": ["Spelunkery меняет добычу самоцветов: сначала вы получаете необработанный камень, который ещё нужно отшлифовать."]},
            {"adv": S + "grindstone", "after": S + "rough_gem", "text": ["Используйте необработанный самоцвет на точиле. Рецепты и подходящие предметы смотрите в JEI."]},
            {"adv": S + "rough_diamond", "after": "minecraft:story/iron_tools", "text": ["Добудьте необработанный алмаз. В этой сборке обычный алмаз не выпадает из руды сразу."]},
            {"adv": S + "diamond_grindstone", "after": S + "rough_diamond", "text": ["Соберите алмазное точило: оно нужно для обработки необработанного алмаза."]},
            {"adv": "minecraft:story/mine_diamond", "after": S + "diamond_grindstone", "text": ["Отшлифуйте необработанный алмаз на алмазном точиле. Теперь доступны алмазное снаряжение и стол зачарований."]},
            {"adv": "minecraft:story/enchant_item", "after": "minecraft:story/mine_diamond", "text": ["Зачаруйте снаряжение перед долгими экспедициями. Запас еды, воды и света всё ещё необходим."]},
            {"adv": S + "glowstick", "after": "minecraft:story/iron_tools", "text": ["Светящиеся палочки помогают в тёмных пещерах. Проверьте их рецепт в JEI."]},
            {"adv": S + "depth_gauge", "after": "minecraft:story/iron_tools", "text": ["Глубиномер пригодится для ориентации, а позже войдёт в изменённый рецепт компаса природы."]},
            {"adv": "galosphere:adventure/silver_ingot", "after": "minecraft:story/iron_tools", "text": ["Серебро пригодится в рецептах Galosphere и компаса исследователя. Его не нужно собирать для каждого следующего шага основного маршрута."]},
        ]},
        {"key": "caves", "title": "3. Карта редких пещер", "icon": "alexscaves:cave_book", "quests": [
            {"adv": A + "cave_tablet", "after": "minecraft:story/iron_tools", "text": ["Ищите подземные хижины Alex’s Caves и пещерные таблички в них. Табличка — начало исследования одного из редких биомов."]},
            {"adv": A + "cave_book", "after": A + "cave_tablet", "text": ["Пещерный путеводитель хранит открытые сведения о биомах и их обитателях. Пользуйтесь им вместе с этим маршрутом."]},
            {"adv": A + "cave_codex", "after": A + "cave_tablet", "text": ["Расшифруйте табличку на столе спелеолога. Подготовьте бумагу и изучите мини-игру в путеводителе."]},
            {"adv": A + "cave_map", "after": A + "cave_codex", "text": ["Из расшифрованного манускрипта создайте карту нужного пещерного биома. Шесть следующих веток можно исследовать в любом порядке.", "Компас природы и компас исследователя в сборке имеют сложные авторские рецепты. Они полезны позже, но не обязательны для первых экспедиций."]},
            *[{"adv": A + ident, "after": A + "cave_map", "text": [hint]} for ident, hint in [
                ("discover_primordial_caves", "Первобытные пещеры дают доступ к динозаврам и янтариту. По авторскому рецепту один янтарит превращается в три огненных стержня: это один из путей к Краю без Незера."),
                ("discover_toxic_caves", "Токсичные пещеры опасны радиацией и кислотой. Здесь есть сера для альтернативного рецепта огненного порошка. Не берите уран без подготовки; подробности защиты читайте в пещерном справочнике."),
                ("discover_magnetic_caves", "Здесь начинаются неодимовые сплавы, магниты и магнитная техника. Продолжение собрано в отдельной дополнительной главе."),
                ("discover_abyssal_chasm", "Подготовьтесь к темноте и долгому погружению. В Подводной бездне есть морские существа, жемчуг, глубоководные руины и торговля с глубинными жителями."),
                ("discover_forlorn_hollows", "Возьмите надёжный источник света. За местными культами и опасными существами скрываются отдельные цепочки достижений."),
                ("discover_candy_cavity", "Конфетный котлован — самостоятельная ветка с необычной едой, существами и снаряжением. Для попадания в Край проходить её целиком не требуется."),
            ]],
        ]},
        {"key": "end", "title": "4. Дорога в Край", "icon": "minecraft:ender_eye", "quests": [
            {"key": "blaze_powder", "title": "Огненный порошок без Незера", "item": "minecraft:blaze_powder", "text": [
                "Авторский рецепт: серная пыль Alex’s Caves + светокаменная пыль = огненный порошок. Светокаменная пыль делается из песка и мерцающей пыли Deeper Caves.",
                "Мерцающую пыль можно получить из светящихся грибов Spelunkery/Quark, скалкового гриба, светящейся рыбы или биолюминесценции. Все варианты и количества смотрите в JEI.",
                "Другой путь: янтарит из первобытных пещер даёт три огненных стержня. Из них делается обычный огненный порошок. Посещать обе пещеры не обязательно."
            ], "icon": "minecraft:blaze_powder"},
            {"key": "pearls", "title": "Жемчуг Края", "item": "minecraft:ender_pearl", "text": ["Соберите жемчуг Края, например с эндерменов. В сборке стоят Enderman Overhaul и другие моды: проверяйте доступные способы получения в JEI."], "icon": "minecraft:ender_pearl"},
            {"key": "eyes", "title": "Очи Края", "item": "minecraft:ender_eye", "text": ["Соедините жемчуг с огненным порошком. Подготовьте запас очей для поиска крепости и заполнения рамок портала.", "Три предметных пункта этой главы служат подсказками. Если вы уже потратили ингредиенты или вставили очи в портал, заново собирать их для продолжения книги не нужно."], "icon": "minecraft:ender_eye"},
            {"adv": "minecraft:story/follow_ender_eye", "text": ["Найдите крепость по очам Края. Мод Stronghold Rework изменяет её устройство, поэтому ищите портал внимательно и отмечайте обратный путь."]},
            {"adv": "minecraft:story/enter_the_end", "after": "minecraft:story/follow_ender_eye", "text": ["Перед прыжком подготовьте оружие, блоки, еду и воду. Заполните пустые рамки портала очами и войдите в Край."]},
            {"adv": "minecraft:end/kill_dragon", "after": "minecraft:story/enter_the_end", "text": ["Разрушьте кристаллы и победите дракона. Better End Island меняет центральный остров; сохраняйте осторожность у края."]},
            {"adv": "minecraft:end/enter_end_gateway", "after": "minecraft:end/kill_dragon", "text": ["После победы используйте врата Края для путешествия к внешним островам."]},
            {"adv": "minecraft:end/find_end_city", "after": "minecraft:end/enter_end_gateway", "text": ["Найдите город Края. Для дальнейших путешествий ищите город с кораблём."]},
            {"adv": "minecraft:end/elytra", "after": "minecraft:end/find_end_city", "text": ["Заберите элитры с корабля. Основной маршрут завершён; дополнительные главы помогут исследовать оставшиеся достижения сборки."]},
        ]},
    ]


def quest_key(spec: dict) -> str:
    return spec.get("adv", "guide/" + spec.get("key", ""))


def resolve_key(value: str) -> str:
    return value if ":" in value else "guide/" + value


def base_quest(key: str, x=0.0, y=0.0) -> dict:
    return {"id": code("quest/" + key), "x": float(x), "y": float(y),
            "hide_details_until_startable": False, "rewards": []}


def chapter(key: str, title: str, group: str, order: int, quests: list, icon="minecraft:book") -> dict:
    return {"id": code("chapter/" + key), "filename": key, "title": title, "icon": icon,
            "group": code("group/" + group), "order_index": order,
            "default_hide_dependency_lines": False, "hide_quest_details_until_startable": False,
            "quests": quests}


def source_group(adv_id: str, all_adv: dict) -> str:
    namespace = adv_id.split(":")[0]
    if namespace != "alexscaves":
        return namespace
    node = adv_id
    seen = set()
    while node in all_adv and node not in seen:
        seen.add(node)
        name = node.rsplit("/", 1)[-1]
        if name in CAVE_NAMES:
            return "alexscaves/" + name
        node = all_adv[node].get("parent", "")
    return namespace


def positions(ids: list[str], all_adv: dict) -> dict:
    """Tree positions preserve native parent relationships without gameplay gates."""
    members = set(ids)
    children = collections.defaultdict(list)
    for key in sorted(ids):
        parent = all_adv[key].get("parent")
        children[parent if parent in members else None].append(key)
    result = {}
    leaf = 0
    active = set()

    def visit(key, depth):
        nonlocal leaf
        if key in active:
            raise ValueError("Cyclic advancement parents at " + key)
        active.add(key)
        ys = [visit(child, depth + 1) for child in children[key]]
        if ys:
            y = (min(ys) + max(ys)) / 2
        else:
            y = leaf * 1.5
            leaf += 1
        result[key] = (depth * 2.5, y)
        active.remove(key)
        return y

    for root in children[None]:
        visit(root, 0)
        leaf += 1
    if len(result) != len(ids):
        raise ValueError("Advancement parent cycle or missing root")
    return result


def generate(root: Path) -> tuple[dict[Path, dict], dict]:
    all_adv = advancements(root)
    outputs = {}
    main_ids = set()
    main_keys = {quest_key(q) for ch in mainline() for q in ch["quests"]}
    for order, ch in enumerate(mainline()):
        quests = []
        for index, spec in enumerate(ch["quests"]):
            key = quest_key(spec)
            q = base_quest(key, index * 2.0 if ch["key"] != "caves" else (index % 5) * 2.5,
                           0 if ch["key"] != "caves" else (index // 5) * 2.0)
            q["description"] = spec["text"]
            task = {"id": code("task/" + key)}
            if "adv" in spec:
                if spec["adv"] not in all_adv or not all_adv[spec["adv"]].get("display"):
                    raise ValueError("Missing main advancement " + spec["adv"])
                main_ids.add(spec["adv"])
                display = all_adv[spec["adv"]]["display"]
                q["title"] = component(display["title"])
                q["icon"] = native_icon(display)
                task.update(type="advancement", advancement=spec["adv"], criterion="")
            else:
                q["title"] = spec["title"]
                q["icon"] = spec["icon"]
                if "item" in spec:
                    task.update(type="item", item=spec["item"], count=1, consume_items=False)
                else:
                    task["type"] = "checkmark"
            after = spec.get("after", [])
            after = [after] if isinstance(after, str) else after
            if any(resolve_key(x) not in main_keys for x in after):
                raise ValueError("Unresolved main dependency")
            if after:
                q["dependencies"] = [code("quest/" + resolve_key(x)) for x in after]
            q["tasks"] = [task]
            quests.append(q)
        outputs[BOOK / "chapters" / (ch["key"] + ".snbt")] = chapter(ch["key"], ch["title"], "main", order, quests, ch["icon"])

    excluded = exclusions(root, all_adv)
    mod_adv = {key for key, data in all_adv.items()
               if not key.startswith("minecraft:") and data.get("display") and key not in excluded}
    groups = collections.defaultdict(list)
    for key in sorted(mod_adv - main_ids):
        groups[source_group(key, all_adv)].append(key)
    for order, (group, ids) in enumerate(sorted(groups.items())):
        key = "extra_" + group.replace("/", "_")
        title = CAVE_NAMES[group.split("/")[1]] if "/" in group else MOD_NAMES.get(group, group)
        coords = positions(ids, all_adv)
        quests = []
        for adv_id in ids:
            display = all_adv[adv_id]["display"]
            q = base_quest(adv_id, *coords[adv_id])
            q.update(title=component(display["title"]), icon=native_icon(display), optional=True,
                     description=[component(display["description"]),
                        "Дополнительная ветка. Расположение повторяет дерево достижений мода, но не закрывает задания: родитель в меню достижений не всегда является условием в игре.",
                        "Поверхность опасна, а Незер закрыт по правилам сборки. Некоторые исходные достижения модов требуют таких мест; они сохранены для справки и не блокируют основной маршрут."],
                     tasks=[{"id": code("task/" + adv_id), "type": "advancement", "advancement": adv_id, "criterion": ""}])
            parent = all_adv[adv_id].get("parent")
            if parent and all_adv.get(parent, {}).get("display"):
                q["description"] += ["Предыдущее достижение в исходном дереве:", component(all_adv[parent]["display"]["title"])]
            quests.append(q)
        outputs[BOOK / "chapters" / (key + ".snbt")] = chapter(key, title, "extra", order, quests)

    outputs[BOOK / "chapter_groups.snbt"] = {"chapter_groups": [
        {"id": code("group/main"), "title": "Основной маршрут", "order_index": 0},
        {"id": code("group/extra"), "title": "Дополнительные достижения", "order_index": 1},
    ]}
    outputs[BOOK / "data.snbt"] = {"version": 13, "title": "Путь сквозь пещеры", "default_consume_items": False,
        "default_autoclaim_rewards": "disabled", "default_reward_team": False, "default_quest_shape": "circle",
        "progression_mode": "flexible", "drop_loot_crates": False, "emergency_items": [],
        "drop_book_on_death": False, "disable_gui": False, "detection_delay": 20, "pause_game": False,
        "grid_scale": 0.5, "show_lock_icons": True}
    all_quests = [q for data in outputs.values() for q in data.get("quests", [])]
    quest_ids = {q["id"] for q in all_quests}
    object_ids = [data["id"] for data in outputs.values() if "id" in data]
    object_ids += [q["id"] for q in all_quests] + [t["id"] for q in all_quests for t in q["tasks"]]
    if len(object_ids) != len(set(object_ids)):
        raise ValueError("Duplicate object IDs")
    for q in all_quests:
        if not set(q.get("dependencies", [])).issubset(quest_ids):
            raise ValueError("Dangling dependency")
    covered = [t["advancement"] for q in all_quests for t in q["tasks"] if t["type"] == "advancement"]
    if not mod_adv.issubset(covered) or len(covered) != len(set(covered)):
        raise ValueError("Missing or duplicate advancement coverage")
    return outputs, {"chapters": len(outputs) - 2, "quests": len(all_quests), "modAdvancements": len(mod_adv),
                     "advancementTasks": len(covered), "rewards": 0, "nativeUnavailable": sorted(excluded),
                     "modNamespaces": dict(sorted(collections.Counter(k.split(":")[0] for k in mod_adv).items()))}


def render(value: dict) -> str:
    # JSON is a strict subset of the SNBT grammar used by FTB Library; keeping
    # quoted keys also makes these artifacts inspectable with ordinary JSON tools.
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def verify_runtime(outputs: dict, snapshot: Path) -> None:
    loaded = set(json.loads(snapshot.read_text(encoding="utf-8"))["advancements"])
    targets = {t["advancement"] for data in outputs.values() for q in data.get("quests", [])
               for t in q["tasks"] if t["type"] == "advancement"}
    missing = targets - loaded
    uncovered_mod = {key for key in loaded if not key.startswith("minecraft:")} - targets
    if missing or uncovered_mod:
        raise ValueError("Native target mismatch; missing=" + str(sorted(missing))
                         + "; uncovered mods=" + str(sorted(uncovered_mod)))


def run(root: Path, verify: bool, snapshot: Path | None = None) -> dict:
    outputs, report = generate(root)
    if snapshot:
        verify_runtime(outputs, snapshot)
    actual = set((root / BOOK).rglob("*.snbt")) if (root / BOOK).exists() else set()
    expected = {root / p for p in outputs}
    unexpected = actual - expected
    if unexpected:
        raise ValueError("Unexpected quest files: " + ", ".join(str(p.relative_to(root)) for p in sorted(unexpected)))
    for path, data in outputs.items():
        target = root / path
        content = render(data)
        if verify:
            if not target.is_file() or target.read_text(encoding="utf-8") != content:
                raise ValueError("Stale or missing quest file: " + str(path))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=ROOT)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--runtime-snapshot", type=Path, help="Native ServerAdvancementManager display snapshot from QA")
    args = parser.parse_args()
    print(json.dumps(run(args.pack.resolve(), args.verify_only, args.runtime_snapshot), ensure_ascii=False, indent=2))
