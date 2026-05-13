create table if not exists alchemist (
    id          int auto_increment primary key,
    name        varchar(120) not null,
    country     varchar(60)  not null,
    birth_year  int not null,
    death_year  int
) character set utf8mb4;

create table if not exists manuscript (
    id            int auto_increment primary key,
    alchemist_id  int references alchemist(id),
    title         varchar(160) not null,
    year_written  int not null,
    language      varchar(40)  not null,
    location      varchar(120) not null
) character set utf8mb4;

create table if not exists ingredient (
    id          int auto_increment primary key,
    name        varchar(120) not null,
    latin_name  varchar(120),
    category    varchar(60)  not null,
    properties  text not null
) character set utf8mb4;

create table if not exists activity (
    id             int auto_increment primary key,
    alchemist_id   int references alchemist(id),
    manuscript_id  int references manuscript(id),
    name           varchar(160) not null,
    goal           varchar(200) not null,
    result         varchar(200) not null,
    duration_days  int not null
) character set utf8mb4;

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

insert into activity (alchemist_id, manuscript_id, name, goal, result, duration_days) values
    (1, 1, 'превращение овса в чугун',         'получить твёрдый завтрак',      'получили мягкий стыд',                      14),
    (1, 2, 'отжимание понедельника из недели', 'сделать неделю шестидневной',   'неделя стала длиннее на полтора дня',       40),
    (2, 3, 'варка эликсира офисной бодрости',  'разбудить писаря до петухов',   'писарь уснул стоя у окна',                   7),
    (3, 4, 'изгнание сонливости из бухгалтера','вернуть бухгалтеру отчёт',      'бухгалтер ушёл в лес и больше не вернулся', 21);
