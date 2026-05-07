create table if not exists alchemist (
    id          serial primary key,
    name        varchar(120) not null,
    country     varchar(60)  not null,
    birth_year  int not null,
    death_year  int
);

create table if not exists manuscript (
    id            serial primary key,
    alchemist_id  int references alchemist(id) on delete cascade,
    title         varchar(160) not null,
    year_written  int not null,
    language      varchar(40)  not null,
    location      varchar(120) not null
);

create table if not exists ingredient (
    id          serial primary key,
    name        varchar(120) not null,
    latin_name  varchar(120),
    category    varchar(60)  not null,
    properties  text not null
);

create table if not exists activity (
    id             serial primary key,
    alchemist_id   int references alchemist(id) on delete cascade,
    manuscript_id  int references manuscript(id) on delete set null,
    name           varchar(160) not null,
    goal           varchar(200) not null,
    result         varchar(200) not null,
    duration_days  int not null
);

create table if not exists activity_ingredient (
    activity_id    int references activity(id)   on delete cascade,
    ingredient_id  int references ingredient(id) on delete cascade,
    primary key (activity_id, ingredient_id)
);

insert into alchemist (name, country, birth_year, death_year) values
    ('гермогор безголовый',         'богемия',     1142, 1219),
    ('брат кукуруз пражский',       'богемия',     1278, 1341),
    ('магистр витольд чесночный',   'литва',       1311, 1390),
    ('сестра пелагея крытая',       'новгород',    1404, 1488),
    ('доктор обмурий пыхтящий',     'фландрия',    1455, 1522),
    ('абу-бандон ибн-кефир',        'кордова',     1188, 1260);

insert into manuscript (alchemist_id, title, year_written, language, location) values
    (1, 'кодекс семидесяти трёх отговорок',           1198, 'латынь',     'монастырь святого ужаса'),
    (1, 'свиток мокрого огня',                        1205, 'латынь',     'башня без дверей'),
    (2, 'трактат о чугунном овсе',                    1320, 'чешский',    'подвал ратуши'),
    (3, 'наставление об изгнании понедельников',      1369, 'латынь',     'келья номер четыре'),
    (4, 'поваренная книга для жабы',                  1466, 'старорус',   'скит на болоте'),
    (5, 'сводный реестр пыхтений',                    1499, 'фламандский','лаборатория под пивоварней'),
    (6, 'эликсиры для верблюда без настроения',       1233, 'арабский',   'медресе в кордове');

insert into ingredient (name, latin_name, category, properties) values
    ('слюна одноногой жабы',          'saliva ranae monopedis',   'животное', 'усиливает уныние, пахнет вторником'),
    ('пепел книжного червя',          'cinis vermis libri',       'минерал',  'вызывает зуд понимания'),
    ('корень нелюбви',                'radix odii tepidi',        'трава',    'горчит, шепчет имена бывших'),
    ('слеза провинциального министра','lacrima ministri',         'жидкость', 'солёная, светится при луне'),
    ('молоко лунного барана',         'lac arietis lunaris',      'жидкость', 'свёртывается от честных слов'),
    ('перо испуганного петуха',       'penna galli pavidi',       'животное', 'дрожит без причины'),
    ('пыль с башмаков нотариуса',     'pulvis calcei notarii',    'минерал',  'делает почерк неразборчивым'),
    ('сушёный смех ребёнка',          'risus pueri siccatus',     'эфир',     'хрустит, отпугивает кредиторов'),
    ('тень от чужой свадьбы',         'umbra nuptiarum alienae',  'эфир',     'липкая, прилипает к зеркалу'),
    ('вытяжка из понедельника',       'extractum diei lunae',     'эфир',     'тяжёлая, тонет в любой воде'),
    ('квас семилетней выдержки',      'cerevisia septennis',      'жидкость', 'кипит при взгляде'),
    ('обрезки чужой совести',         'frusta conscientiae',      'эфир',     'не имеет веса, мешает спать');

insert into activity (alchemist_id, manuscript_id, name, goal, result, duration_days) values
    (1, 1, 'превращение овса в чугун',                  'получить твёрдый завтрак',           'получили мягкий стыд',                      14),
    (1, 2, 'отжимание понедельника из недели',          'сделать неделю шестидневной',        'неделя стала длиннее на полтора дня',       40),
    (2, 3, 'варка эликсира офисной бодрости',           'разбудить писаря до петухов',        'писарь уснул стоя у окна',                   7),
    (3, 4, 'изгнание сонливости из бухгалтера',         'вернуть бухгалтеру отчёт',           'бухгалтер ушёл в лес и больше не вернулся', 21),
    (4, 5, 'окрашивание тоски в зелёный',               'сделать тоску переносимой',          'тоска стала красивой и заразной',           33),
    (5, 6, 'дистилляция жидкого воскресенья',           'продлить выходной до среды',         'воскресенье испарилось вместе с пятницей',   9),
    (6, 7, 'настойка на верблюжьем недовольстве',       'снять усталость каравана',           'верблюды объявили забастовку',              18),
    (3, 4, 'трансмутация чужого мнения',                'превратить осуждение в одобрение',   'все молча ушли пить',                       12);

insert into activity_ingredient (activity_id, ingredient_id) values
    (1, 1), (1, 5), (1, 11),
    (2, 10), (2, 9), (2, 8),
    (3, 11), (3, 6), (3, 4),
    (4, 3), (4, 12), (4, 8),
    (5, 9), (5, 3), (5, 4),
    (6, 10), (6, 5), (6, 8),
    (7, 5), (7, 6),
    (8, 12), (8, 7), (8, 9);
