"""
Import Washington state school district superintendent contact information
from OSPI EDS Directory into Supabase PostgreSQL.
"""

import psycopg2
import re
import uuid

# Raw data scraped from https://eds.ospi.k12.wa.us/DirectoryEDS.aspx
RAW_DATA = """Aberdeen School District | Lynn Green | (360)538-2000 | lgreen@asd5.org
Adna School District | Thad Nelson | (360)748-0362 | nelsont@adnaschools.org
Almira School District | Timothy A Payne | (509)639-2414 | tpayne@almirasd.org
Anacortes School District | Carl Bruner | (360)503-1210 | cbruner@asd103.org
Arlington School District | Chrys Sweeting | (360)618-6202 | chrys.sweeting@asd16.org
Asotin-Anatone School District | Dale Bonfield | (509)243-1100 | dbonfield@aasd.wednet.edu
Auburn School District | Alan Spicciati | (253)931-4914 | aspicciati@auburn.wednet.edu
Bainbridge Island School District | Amii Thompson | (206)780-1067 | athompson@bisd303.org
Battle Ground School District | Shelly Whitten | (360)885-5302 | whitten.shelly@battlegroundps.org
Bellevue School District | Kelly Aramaki | (425)456-4000 | aramakik@bsd405.org
Bellingham School District | Greg Baker | (360)676-6470 | greg.baker@bellinghamschools.org
Benge School District | Suzanne Schmick | (509)887-2370 | suzanne.schmick@benge.wednet.edu
Bethel School District | Brian M Lowney | (253)800-2010 | blowney@bethelsd.org
Bickleton School District | Regan Alires | (509)896-5473 | ralires@bickletonschools.org
Blaine School District | Daniel Chaplik | (360)332-5881 | dchaplik@blainesd.org
Boistfort School District | Neil Varble | (360)245-3343 | nvarble@boistfort.k12.wa.us
Bremerton School District | Slade McSheehy | (360)473-1006 | slade.mcsheehy@bremertonschools.org
Brewster School District | Eric Driessen | (509)689-3418 | edriessen@brewsterbears.org
Bridgeport School District | Scott Sattler | (509)686-5656 | ssattler@bsd75.org
Brinnon School District | Patricia Beathard | (360)796-4646 | pbeathard@bsd46.org
Burlington-Edison School District | Chris Pearson | (360)757-3311 | cpearson@be.wednet.edu
Camas School District | John Anzalone | (360)335-3000 | john.anzalone@camas.wednet.edu
Cape Flattery School District | Michelle Parkin | (360)780-6531 | mparkin@cfsd401.org
Carbonado School District | Jessie Sprouse | (360)829-0121 | jsprouse@carbonado.k12.wa.us
Cascade School District | Tracey Edou | (509)548-5885 | tedou@cascadesd.org
Cashmere School District | Glenn Erick Johnson | (509)782-3355 | gjohnson@cashmere.wednet.edu
Castle Rock School District | Chris Fritsch | (360)501-2940 | cfritsch@crschools.org
Catalyst Public Schools | Amanda Gardner | (360)207-0229 | amanda@catalystpublicschools.org
Centerville School District | Ann Varkados | (509)773-4893 | avarkados@centervilleschool.org
Central Kitsap School District | Erin Prince | (360)662-1610 | erinp@ckschools.org
Central Valley School District | John Parker | (509)558-5404 | jparker@cvsd.org
Centralia School District | Lisa Grant | (360)330-7600 | lgrant@centralia.wednet.edu
Chehalis School District | Rick Goble | (360)807-7200 | rgoble@chehalisschools.org
Cheney School District | Ben Ferney | (509)559-4500 | bferney@cheneysd.org
Chewelah School District | Jason Perrins | (509)685-6800 | jperrins@chewelahk12.us
Chief Leschi Tribal Compact | Don Brummett | (253)445-6000 | don.brummett@leschischools.org
Chimacum School District | Scott Mauk | (360)302-5896 | scott_mauk@csd49.org
Clarkston School District | Thaynan Knowlton | (509)758-2531 | knowltont@csdk12.org
Cle Elum-Roslyn School District | John Belcher | (509)852-4836 | belcherj@cersd.org
Clover Park School District | Ron Banner | (253)583-5060 | rbanner@cloverpark.k12.wa.us
Colfax School District | Jerry Pugh | (509)397-3042 | jerry.pugh@csd300.org
College Place School District | Jim Fry | (509)525-4827 | jfry@cpps.org
Colton School District | Jody Moehrle | (509)229-3385 | jodymoehrle@colton.k12.wa.us
Columbia (Stevens) School District | Gregory Price | (509)722-3311 | gprice@columbia206.net
Columbia (Walla Walla) School District | Todd Hilberg | (509)547-2136 | todd.hilberg@csd400.org
Colville School District | Kevin Knight | (509)684-7850 | kknight@colsd.org
Concrete School District | Carrie Crickmore | (360)853-4000 | ccrickmore@concrete.k12.wa.us
Conway School District | Jeff Cravy | (360)445-5785 | jcravy@conway.k12.wa.us
Cosmopolis School District | Jennifer Sikes | (360)531-7181 | jsikes@cosmopolisschool.com
Coulee-Hartline School District | Kelley Boyd | (509)632-5231 | kboyd@achwarriors.com
Coupeville School District | Shannon Leatherwood | (360)678-2404 | sleatherwood@coupeville.k12.wa.us
Crescent School District | David Bingham | (360)928-3311 | dbingham@csd313.org
Creston School District | Jay Tyus | (509)429-5067 | jtyus@wcsd.wednet.edu
Curlew School District | Wyatt Ladiges | (509)779-4931 | wladiges@curlewsd.org
Cusick School District | Don Hawpe | (509)445-1125 | dhawpe@cusick.wednet.edu
Damman School District | Timothy P. Lawless | (509)962-9079 | timothy.lawless@dammanschool.org
Darrington School District | Tracy Franke | (360)436-1323 | tfranke@dsd.k12.wa.us
Davenport School District | Chad Prewitt | (509)725-1481 | cprewitt@davenportsd.org
Dayton School District | Jeremy Wheatley | (509)382-2543 | jeremyw@daytonsd.org
Deer Park School District | Alexa Allman | (509)464-5507 | alexa.allman@dpsdmail.org
Dieringer School District | Paula Dawson | (253)862-2537 | pdawson@dieringer.wednet.edu
Dixie School District | Jacob D Bang | (509)525-5339 | jbang@dixiesd.org
East Valley School District (Spokane) | Brian Talbott | (509)241-5032 | talbottb@evsd.org
East Valley School District (Yakima) | Russell Hill | (509)573-7320 | hill.russ@evsd90.org
Eastmont School District | Spencer Taylor | (509)884-7169 | taylors@eastmont206.org
Easton School District | Aaron Kombol | (509)656-2317 | kombola@easton.wednet.edu
Eatonville School District | Lucy Fountain | (360)879-1000 | l.fountain@eatonville.wednet.edu
Edmonds School District | Rebecca Miner | (425)431-7001 | minerr@edmonds.wednet.edu
Ellensburg School District | Troy Tornow | (509)925-8010 | Troy.tornow@esd401.org
Elma School District | Chris Nesmith | (360)482-2822 | cnesmith@eagles.edu
Endicott School District | Tricia Jeffries | (509)657-3523 | tjeffries@sjeschools.org
Entiat School District | Greg Whitmore | (509)784-1800 | gwhitmore@entiatschools.org
Enumclaw School District | Jill Burnes | (360)802-7102 | jill_burnes@enumclaw.wednet.edu
Ephrata School District | Ken Murray | (509)754-2474 | kmurray@ephrataschools.org
Evaline School District | Kyle MacDonald | (360)785-3460 | kmacdonald@evalinesd.k12.wa.us
Everett School District | Ian Saltzman | (425)385-4019 | ISaltzman@everettsd.org
Evergreen School District (Clark) | Christine Moloney | (360)604-4000 | christine.moloney@evergreenps.org
Evergreen School District (Stevens) | Paul Clark | (509)936-6021 | pclark@evergreen.k12.wa.us
Federal Way School District | Dani Pfeiffer | (253)945-2000 | dpfeiffe@fwps.org
Ferndale School District | Karin Kristi Dominguez | (360)383-9207 | kristi.dominguez@ferndalesd.org
Fife School District | Kevin Alfano | (253)517-1000 | kalfano@fifeschools.com
Finley School District | Bryan Long | (509)586-3217 | blong@finleysd.org
Franklin Pierce School District | Lance Goodpaster | (253)298-3010 | lgoodpaster@fpschools.org
Freeman School District | Randy L. Russell | (509)291-3695 | rrussell@freemansd.org
Goldendale School District | Ellen Perconti | (509)773-5177 | ellen.perconti@gsd404.org
Grand Coulee Dam School District | Rodriguez Broadnax | (509)633-2143 | rbroadnax@gcdsd.org
Grandview School District | Rob T Darling | (509)882-8500 | rtdarling@gsd200.org
Granger School District | Brian Hart | (509)854-1515 | hartb@gsd.wednet.edu
Granite Falls School District | Dana Geaslen | (360)691-7717 | dgeaslen@gfalls.wednet.edu
Grapeview School District | Gerald Grubbs | (360)426-4921 | ggrubbs@gsd54.org
Great Northern School District | Kelly Shea | (509)747-7714 | kshea@gnsd.k12.wa.us
Green Mountain School District | David R Holmes | (360)225-7366 | dave.holmes@greenmountainschool.us
Griffin School District | Kirsten Rue | (360)866-2515 | krue@griffinschool.us
Harrington School District | Courtney Strozyk | (509)253-4331 | cstrozyk@harringtonsd.org
Highland School District | Mindy Schultz | (509)678-8635 | mschultz@highland.wednet.edu
Highline School District | Ivan Duran | (206)631-3000 | ivan.duran@highlineschools.org
Hockinson School District | Steven Marshall | (360)448-6400 | steve.marshall@hocksd.org
Hood Canal School District | Lance Gibbon | (360)877-5463 | lgibbon@hoodcanalschool.org
Hoquiam School District | Mike Villarreal | (360)538-8200 | mvillarreal@hoquiam.net
Inchelium School District | Brian Freeman | (509)722-6181 | bfreeman@inchelium.net
Index School District | Gerald E Grubbs | (360)793-1330 | ggrubbs@index.k12.wa.us
Issaquah School District | Heather Tow-Yick | (425)837-7002 | TowYickH@issaquah.wednet.edu
Kahlotus School District | Andie Webb | (509)282-3338 | andie.webb@kahlotussd.org
Kalama School District | Wesley Benjamin | (360)673-5282 | wesley.benjamin@kalama.k12.wa.us
Keller School District | Steve Jantz | (509)634-4325 | sjantz@keller.k12.wa.us
Kelso School District | Mary Beth Tack | (360)501-1927 | marybeth.tack@kelsosd.org
Kennewick School District | Lance Hansen | (509)222-5020 | lance.hansen@ksd.org
Kent School District | Israel Vela | (253)373-7701 | Israel.Vela@kent.k12.wa.us
Kettle Falls School District | Michael Olsen | (509)738-6625 | molsen@kfschools.org
Kiona-Benton City School District | Pete Peterson | (509)588-2000 | pete.peterson@kibesd.org
Kittitas School District | Tim Praino | (509)955-3120 | tim_praino@ksd403.org
Klickitat School District | Kendrick Lester | (509)369-4145 | kendrick.lester@klickitatsd.org
La Center School District | Peter Rosenkranz | (360)263-2131 | peter.rosenkranz@lacenterschools.org
La Conner School District | David Cram | (360)466-3171 | dcram@lc.k12.wa.us
LaCrosse School District | Doug Curtis | (509)549-3591 | dcurtis@lacrossesd.k12.wa.us
Lake Chelan School District | Brad Wilson | (509)682-3515 | wilsonb@chelanschools.org
Lake Quinault School District | Keith Samplawski | (360)288-2260 | ksamplawski@lakequinaultschools.org
Lake Stevens School District | Mary Templeton | (425)335-1505 | mary_templeton@lkstevens.wednet.edu
Lake Washington School District | Jonathon Holmen | (425)936-1257 | Superintendent@lwsd.org
Lakewood School District | Erin Murphy | (360)652-4500 | emurphy@lwsd.wednet.edu
Lamont School District | Shannon Hughes | (509)257-2463 | shughes@lamont.wednet.edu
Liberty School District | Jerrad Jeske | (509)624-4415 | jjeske@libertysd.us
Lind School District | Gary Wargo | (509)677-3499 | gwargo@lrschools.org
Longview School District | Karen Lynn Cloninger | (360)575-7016 | kcloninger@longview.k12.wa.us
Loon Lake School District | Bradley Van Dyne | (509)233-2212 | bvandyne@loonlakeschool.org
Lopez Island School District | Brady Payne Smith | (360)468-2202 | bsmith@lopezislandschool.org
Lyle School District | Ann Varkados | (509)365-2191 | ann.varkados@lyleschools.org
Lynden School District | David VanderYacht | (360)354-4443 | vanderyachtd@lynden.wednet.edu
Mabton School District | Elyse Mengarelli | (509)894-4852 | mengarellie@msd120.org
Mansfield School District | Bruce Todd | (509)683-1012 | btodd@mansfield.wednet.edu
Manson School District | Tabatha Mires | (509)687-3140 | tmires@manson.org
Mary M Knight School District | Matthew Mallery | (360)426-6767 | mmallery@mmk.wednet.edu
Mary Walker School District | Todd Spear | (509)258-4702 | tspear@marywalker.org
Marysville School District | Deborah Rumbaugh | (360)965-0001 | deborah_rumbaugh@msd25.org
McCleary School District | Susan Zetty | (360)495-3204 | szetty@mccleary.wednet.edu
Mead School District | Travis W Hanson | (509)465-6014 | travis.hanson@mead354.org
Medical Lake School District | Kimberly Headrick | (509)565-3100 | kheadrick@mlsd.org
Mercer Island School District | Fred Rundle | (206)236-5636 | fred.rundle@mercerislandschools.org
Meridian School District | James E Everett | (360)398-7111 | jeverett@meridian.wednet.edu
Methow Valley School District | Grant Storey | (509)996-9205 | gstorey@methow.org
Mill A School District | Kelly Stickel | (509)538-2700 | kelly.stickel@millasd.org
Monroe School District | Shawn Woodward | (360)804-2500 | woodwards@monroe.wednet.edu
Montesano School District | Dan Winter | (360)249-3942 | dwinter@monteschools.org
Morton School District | John Hannah | (360)496-5300 | jhannah@morton.k12.wa.us
Moses Lake School District | Carol Lewis | (509)766-2650 | clewis@mlsd161.org
Mossyrock School District | Hayward Mark Chandler | (360)983-3181 | mchandler@mossyrockschools.org
Mount Adams School District | Curt Guaglianone | (509)874-2611 | cguaglianone@masd209.org
Mount Baker School District | Jessica Schenck | (360)383-2000 | jschenck@mtbaker.wednet.edu
Mount Pleasant School District | Cathy Lehmann | (360)835-3371 | cathy.lehmann@mtpleasantschool.org
Mount Vernon School District | Victor Vergara | (360)428-6181 | vvergara@mvsd320.org
Mukilteo School District | Alison Brynelson | (425)356-1220 | BrynelsonAX@mukilteo.wednet.edu
Naches Valley School District | Robert Bowman | (509)653-2220 | rbowman@nvsd.org
Napavine School District | Shane Schutz | (360)262-3303 | sschutz@napavineschools.org
Naselle-Grays River Valley School District | Joshua Brooks | (360)484-7121 | jbrooks@naselleschools.org
Nespelem School District | Effie Dean | (509)634-4541 | edean@nsdeagles.org
Newport School District | David E. Smith | (509)447-3167 | smithdave@newportgriz.com
Nine Mile Falls School District | Jeffrey P Baerwald | (509)340-4303 | JBaerwald@9mile.org
Nooksack Valley School District | Matt Galley | (360)988-4754 | matt.galley@nv.k12.wa.us
North Beach School District | Richard Zimmerman | (360)289-2447 | rzimmerman@northbeachschools.org
North Franklin School District | Brian Moore | (509)234-2021 | bmoore@nfsd.org
North Kitsap School District | Rachel Davenport | (360)396-3000 | RDavenport@nkschools.org
North Mason School District | Kristine Michael | (360)277-2300 | kmichael@northmasonschools.org
North River School District | Pamela Pratt | (564)201-0388 | pampratt@nr.k12.wa.us
North Thurston Public Schools | Troy Oliver | (360)412-4413 | superintendent@ntps.org
Northport School District | Catherine Hunt | (509)732-4251 | drhunt@northportschools.org
Northshore School District | Justin Irish | (425)408-6000 | jirish@nsd.org
Oak Harbor School District | Michelle Kuss-Cybula | (360)279-5008 | mkuss-cybula@ohsd.net
Oakesdale School District | Jake Dingman | (509)285-5296 | jdingman@gonighthawks.net
Oakville School District | Richard Staley | (360)273-0171 | rstaley@oakvilleschools.org
Ocean Beach School District | Amy Huntley | (360)642-3739 | amy.huntley@oceanbeachschools.org
Ocosta School District | Heather Sweet | (360)268-9125 | hsweet@ocosta.org
Odessa School District | Steve Fisk | (509)982-2668 | fisks@odessasd.org
Okanogan School District | Steve Quick | (509)422-3629 | squick@oksd.wednet.edu
Olympia School District | Patrick Murphy | (360)596-6117 | pmurphy@osd.wednet.edu
Omak School District | Michael L Porter | (509)826-0320 | mporter@omaksd.org
Onalaska School District | Brenda Padgett | (360)978-4111 | bpadgett@onysd.wednet.edu
Onion Creek School District | Dan Read | (509)732-4240 | dread@ocsd30.org
Orcas Island School District | Eric Webb | (360)376-1501 | ewebb@orisd.org
Orchard Prairie School District | Joseph Beckford | (509)467-9517 | jbeckford@orchardprairie.org
Orient School District | Sherry Cowbrough | (509)684-6873 | sherry.cowbrough@orientsd.org
Orondo School District | Stephanie Andler | (509)784-2443 | sandler@orondo.wednet.edu
Oroville School District | Jeff Hardesty | (509)476-2281 | jeff.hardesty@oroville.wednet.edu
Orting School District | William Edward Hatzenbeler | (360)893-4024 | hatzenbelere@orting.wednet.edu
Othello School District | Pete Perez | (509)488-2659 | pperez@othelloschools.org
Palisades School District | Stephanie Andler | (509)884-8071 | sandler@palisades.wednet.edu
Palouse School District | Mike Jones | (509)878-1921 | mjones@garpal.net
Pasco School District | Michelle I. Whitney | (509)543-6700 | mwhitney@psd1.org
Pateros School District | Scotti Wiltse | (509)923-2751 | swiltse@pateros.org
Paterson School District | Joe West | (509)875-2601 | joewe@patersonschool.org
Pe Ell School District | Kyle MacDonald | (360)291-3244 | kmacdonald@peell.k12.wa.us
Peninsula School District | Krestin Bahr | (253)530-1002 | bahrk@psd401.net
Pioneer School District | Jeff A. Davis | (360)426-9115 | jdavis@psd402.org
Port Angeles School District | Michelle Olsen | (360)457-8575 | molsen@portangelesschools.org
Port Townsend School District | Linda Rosenbury | (360)680-5759 | lrosenbury@ptschools.org
Prescott School District | Jeff Foertsch | (509)849-2217 | jfoertsch@prescott.k12.wa.us
Prosser School District | Kimberly Casey | (509)786-3323 | kimberly.casey@prosserschools.org
Pullman School District | Robert Maxwell | (509)332-3144 | rmaxwell@psd267.org
Puyallup School District | Richard Lasso | (253)840-8950 | LassoR@puyallupsd.org
Queets-Clearwater School District | Mel Houtz | (360)962-2395 | mhoutz@qcsd20.org
Quilcene School District | Ronald C Moag | (360)765-2902 | rmoag@qsd48.org
Quillayute Valley School District | Diana Reaume | (360)374-6262 | diana.reaume@qvschools.org
Quincy School District | Nikolas Bergman | (509)787-4571 | nbergman@qsd.wednet.edu
Rainier School District | Bryon Bahr | (360)446-2207 | bahrb@rainier.wednet.edu
Raymond School District | K.C. Johnson | (360)942-3415 | kcjohnson@raymondk12.org
Reardan-Edwall School District | Eric J Sobotta | (509)869-3231 | esobotta@reardansd.net
Renton School District | Damien Pattenaude | (425)204-2341 | damien.pattenaude@rentonschools.us
Republic School District | John Farley | (509)775-3173 | jfarley@republicsd.org
Richland School District | Shelley Redinger | (509)967-6001 | Shelley.Redinger@rsd.edu
Ridgefield School District | Jenny Rodriquez | (360)619-1302 | jenny.rodriquez@ridgefieldsd.org
Ritzville School District | Gary Wargo | (509)659-1660 | gwargo@lrschools.org
Riverside School District | Ken Russell | (509)464-8201 | ken.russell@rsdmail.org
Riverview School District | Susan Leach | (425)844-4503 | leachs@rsd407.org
Rochester School District | Jennifer Bethman | (360)273-9242 | jbethman@rochester.wednet.edu
Roosevelt School District | Erin Lucich | (509)384-5462 | erin.lucich@rooseveltschooldistrict.net
Rosalia School District | Julie Price | (509)523-3061 | jprice@rosaliaschools.org
Royal School District | Roger Trail | (509)346-2222 | rtrail@royalsd.org
San Juan Island School District | Calvin Frederick Woods | (360)370-7905 | fredwoods@sjisd.org
Satsop School District | Tiffany Osgood | (360)482-5330 | tosgood@satsopschool.org
Seattle Public Schools | Brent Jones | (206)252-0180 | superintendent@seattleschools.org
Selah School District | Kevin McKay | (509)698-8002 | kevinmckay@selahschools.org
Selkirk School District | Nancy Lotze | (509)446-2951 | nlotze@selkirkschools.org
Sequim School District | Regan Nickels | (360)582-3260 | rnickels@sequimschools.org
Shaw Island School District | Becky Bell | (360)468-2570 | bbell@shaw.k12.wa.us
Shelton School District | Wyeth Jessee | (360)426-1687 | wjessee@sheltonschools.org
Shoreline School District | Susana Reyes | (206)393-4203 | susana.reyes@ssd412.org
Skamania School District | Katie Chavarria | (509)427-8239 | kchavarria@skamania.k12.wa.us
Skykomish School District | Destry K Jones | (425)324-1025 | djones@skykomish.wednet.edu
Snohomish School District | Kent Kultgen | (360)563-7280 | Kent.Kultgen@sno.wednet.edu
Snoqualmie Valley School District | Daniel T Schlotfeldt | (425)831-8018 | schlotfeldtd@svsd410.org
Soap Lake School District | Angela Rolfe | (509)246-1822 | arolfe@slschools.org
South Bend School District | Jon Tienhaara | (360)875-6041 | jtienhaa@southbendschools.org
South Kitsap School District | Tim Winter | (360)874-7000 | winter@skschools.org
South Whidbey School District | Rebecca Clifford | (360)221-6100 | bclifford@sw.wednet.edu
Southside School District | Paul Wieneke | (360)426-8437 | pwieneke@southsideschool.org
Spokane School District | Adam Swinyard | (509)354-7364 | AdamSw@SpokaneSchools.org
Sprague School District | Raymond Leaver | (509)257-2591 | rleaver@sprague.wednet.edu
St. John School District | Tina Strong | (509)397-8058 | tstrong@sjeschools.org
Stanwood-Camano School District | Ryan Ovenell | (360)629-1200 | rovenell@stanwood.wednet.edu
Star School District No. 054 | Lance Hahn | (509)995-7256 | lhahn@starsd.org
Starbuck School District | Mark Pickel | (509)399-2381 | mpickel@starbuck.k12.wa.us
Stehekin School District | Michelle Price | (509)665-2628 | michellep@ncesd.org
Steilacoom Hist. School District | Kathi Weight | (253)983-2200 | kweight@steilacoom.k12.wa.us
Steptoe School District | Eric D Patton | (509)397-3119 | ericp@steptoe.k12.wa.us
Stevenson-Carson School District | Ingrid Colvard | (509)427-5674 | colvardi@scsd303.org
Sultan School District | Chris Granger | (360)793-9800 | chris.granger@sultan.k12.wa.us
Summit Valley School District | Kristina Allen | (509)935-6362 | kallen@svalley.k12.wa.us
Sumner-Bonney Lake School District | Laurie Dent | (253)891-6080 | laurie_Dent@sumnersd.org
Sunnyside School District | Ryan Maxwell | (509)837-5851 | ryan.maxwell@sunnysideschools.org
Tacoma School District | Joshua Garcia | (253)571-1010 | jgarcia2@tacoma.k12.wa.us
Taholah School District | Herman J Lartigue Jr. | (360)276-4780 | Hlartigue@taholah.org
Tahoma School District | Ginger Callison | (425)413-3400 | vcalliso@tahomasd.us
Tekoa School District | Michael Jones | (509)284-3281 | mjones@tekoasd.org
Tenino School District | Clinton Endicott | (360)264-3421 | Endicottc@tenino.k12.wa.us
Thorp School District | Andrew Perkins | (509)964-2107 | perkinsa@THORPSCHOOLS.ORG
Toledo School District | Brennan Foster Bailey | (360)864-2325 | bbailey@toledoschools.us
Tonasket School District | Kevin Young | (509)486-2126 | kevin.young@tonasket.wednet.edu
Toppenish School District | Toron Wooldridge | (509)865-4455 | twooldridge@toppenish.wednet.edu
Touchet School District | Robert Elizondo | (509)394-2352 | relizondo@touchet.k12.wa.us
Toutle Lake School District | Chris Schumaker | (360)274-6182 | cschumaker@toutlesd.org
Trout Lake School District | Jerry Lewis | (509)395-2571 | j.lewis@tlschool.net
Tukwila School District | Concie Pedroza | (206)901-8003 | pedrozac@tukwila.wednet.edu
Tumwater School District | Kevin Bogatin | (360)709-7000 | kevin.bogatin@tumwater.k12.wa.us
Union Gap School District | Tom Brandt | (509)654-7985 | tbrandt@uniongap.org
University Place School District | Jeff Chamberlin | (253)566-5600 | jchamberlin@upsd83.org
Valley School District | Mandi Rehn | (509)937-2770 | mandi.rehn@valleysd.org
Vancouver School District | Brett Blechschmidt | (360)313-1341 | Brett.Blechschmidt@vansd.org
Vashon Island School District | Josephine Moccia | (206)463-8534 | jmoccia@vashonsd.org
Wahkiakum School District | Ralph Watkins | (360)795-3971 | rwatkins@wahksd.k12.wa.us
Wahluke School District | Andrew Harlow | (509)932-4565 | anharlow@wahluke.net
Waitsburg School District | Monty Sabin | (509)337-6301 | msabin@waitsburgsd.org
Walla Walla Public Schools | Benjamin Gauyan | (509)526-6715 | bgauyan@wwps.org
Wapato School District | Ezequiel Kelly Garza | (509)877-4181 | kellyg@wapatosd.org
Warden School District | Marc Brouillet | (509)349-2366 | mbrouillet@warden.wednet.edu
Washougal School District | Aaron Hansen | (360)954-3000 | aaron.hansen@washougalsd.org
Washtucna School District | Staci Gloyn | (509)646-3211 | sgloyn@tucna.wednet.edu
Wellpinit School District | John Adkins | (509)258-4535 | jadkins@wellpinit.org
Wenatchee School District | Kory Kalahar | (509)663-8161 | kalahar.k@wenatcheeschools.org
West Valley School District (Spokane) | Kyle Rydell | (509)924-2150 | kyle.rydell@wvsd.org
West Valley School District (Yakima) | Peter D Finch | (509)972-6002 | finchp@WVSD208.ORG
White Pass School District | Paul Farris | (360)497-3791 | pfarris@whitepass.k12.wa.us
White River School District | Scott Harrison | (360)829-3814 | sharrison@whiteriver.wednet.edu
White Salmon Valley School District | Richard Polkinghorn | (509)493-1500 | rich.polkinghorn@whitesalmonschools.org
Wilbur School District | Jay Tyus | (509)429-5067 | jtyus@wcsd.wednet.edu
Wilson Creek School District | Kandice L Hansen | (509)345-2541 | khansen@wilsoncreek.org
Winlock School District | Michelle Jeffries | (360)785-3582 | mjeffries@winlock.wednet.edu
Wishkah Valley School District | Rich Rasanen | (360)532-3128 | rrasanen@wishkah.org
Wishram School District | Tye Churchwell | (509)767-6090 | tye.churchwell@wishramschool.org
Woodland School District | Asha Riley | (360)841-2706 | rileya@woodlandschools.org
Yakima School District | Trevor Greene | (509)573-7001 | greene.trevor@ysd7.org
Yelm School District | Christopher Woods | (360)458-6178 | christopher_woods@ycs.wednet.edu
Zillah School District | Doug Burge | (509)829-5911 | doug.burge@zillahschools.org
Innovation Spokane Schools | Sara Kennedy | (509)309-7680 | sarak@innovationspokane.org
Lumen Public School | Shauna Edwards | (509)570-3921 | sedwards@lumenhighschool.org
Pinnacles Prep | Jill Fineis | (509)888-6464 | info@Pinnaclesprep.org
Rainier Prep Charter School District | Karen Lobos | (206)494-5979 | klobos@rainierprep.org
Rainier Valley Leadership Academy | Baionne Coleman | (206)659-0956 | baionne.coleman@myrvla.org
Rooted School Vancouver | Jamila Singleton | (360)200-8974 | jsingleton@rootedschoolvancouver.org
Spokane International Academy | Morgen Flowers | (509)209-8730 | flowers@spokaneintlacademy.org
Summit Public School: Atlas | Cady Ching | (650)753-9713 | cching@summitps.org
Summit Public School: Sierra | Cady Ching | (650)753-9713 | cching@summitps.org
Why Not You Academy | Abigail O'Neal | (253)324-3676 | aoneal@wnyacademy.org
Chief Leschi Tribal Compact | Don Brummett | (253)445-6000 | don.brummett@leschischools.org
Muckleshoot Indian Tribe | Eric Wyand | (253)931-6709 | Eric.Wyand@muckleshoot.com
Quileute Tribal School District | Bob Harmon | (360)963-4122 | bob.harmon@qtschools.org
Suquamish Tribal Education Department | Brenda Guerrero | (360)394-8460 | bguerrero@suquamish.nsn.us
WA HE LUT Indian School Agency | Harvey Whitford | (253)691-5018 | harvey.whitford@bie.edu
Yakama Nation Tribal Compact | Raynel O. Begay | (509)865-4778 | raynel_begay@yakama.com"""


def parse_name(full_name):
    """Parse a full name into prefix, first_name, last_name, suffix."""
    full_name = full_name.strip()
    # Remove "Dr." prefix
    prefix = None
    if full_name.startswith("Dr. "):
        prefix = "Dr."
        full_name = full_name[4:].strip()

    # Remove common suffixes
    suffix = None
    for s in ["Jr.", "Sr.", "III", "II", "IV"]:
        if full_name.endswith(" " + s):
            suffix = s
            full_name = full_name[: -(len(s) + 1)].strip()
            break

    parts = full_name.split()
    if len(parts) == 0:
        return prefix, "", "", suffix
    elif len(parts) == 1:
        return prefix, parts[0], "", suffix
    else:
        first_name = parts[0]
        last_name = parts[-1]
        # If middle initials/names exist, include first name only
        return prefix, first_name, last_name, suffix


def clean_phone(phone):
    """Clean phone number - strip extensions for storage."""
    if not phone:
        return None
    # Remove extension info for clean storage
    phone = re.split(r'\s*Ext\.', phone)[0].strip()
    return phone


def normalize_district_name(name):
    """Create normalized version for matching."""
    name = name.lower().strip()
    # Remove common suffixes for matching
    for suffix in [" school district", " school dist", " sd"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    # Remove parenthetical qualifiers like (Spokane), (Yakima), (Clark), (Stevens), (Walla Walla)
    name = re.sub(r'\s*\(.*?\)\s*', ' ', name).strip()
    return name


def main():
    # Parse the raw data
    records = []
    for line in RAW_DATA.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 4:
            print(f"  SKIP malformed line: {line}")
            continue
        district_name, admin_name, phone, email = parts
        prefix, first_name, last_name, suffix = parse_name(admin_name)
        phone = clean_phone(phone)
        records.append({
            "district_name": district_name,
            "first_name": first_name,
            "last_name": last_name,
            "prefix": prefix,
            "suffix": suffix,
            "email": email,
            "phone": phone,
        })

    print(f"Parsed {len(records)} superintendent records from OSPI EDS directory")

    # Connect to database
    conn = psycopg2.connect(
        host="aws-0-us-west-2.pooler.supabase.com",
        port=6543,
        dbname="postgres",
        user="postgres.mymxwesilduzjfniecky",
        password="GdguFo6u90xogV9A",
        sslmode="require",
    )
    cur = conn.cursor()

    # Fetch existing WA districts
    cur.execute("SELECT id, name FROM districts WHERE state = 'WA'")
    db_districts = cur.fetchall()
    print(f"Found {len(db_districts)} WA districts in database")

    # Build lookup: normalized name -> (id, original_name)
    # Also build secondary lookups for flexible matching
    district_lookup = {}
    for did, dname in db_districts:
        norm = normalize_district_name(dname)
        district_lookup[norm] = (did, dname)

    # Match and insert
    matched = 0
    skipped = 0
    duplicates = 0
    unmatched = []

    for rec in records:
        ospi_norm = normalize_district_name(rec["district_name"])

        # Try exact normalized match first
        match = district_lookup.get(ospi_norm)

        # Try additional matching strategies
        if not match:
            # Try without "School District" in OSPI name and match against DB names
            for db_norm, (did, dname) in district_lookup.items():
                if ospi_norm == db_norm:
                    match = (did, dname)
                    break
                # Substring matching: one contains the other
                if ospi_norm in db_norm or db_norm in ospi_norm:
                    match = (did, dname)
                    break

        # Try more aggressive matching for known patterns
        if not match:
            # Handle "Hist." -> "Historical", "St." -> "Saint", etc.
            alt_name = ospi_norm.replace("hist.", "historical").replace("st.", "saint")
            match = district_lookup.get(alt_name)

        if not match:
            unmatched.append(rec["district_name"])
            skipped += 1
            continue

        district_id = match[0]

        # Check for existing superintendent contact for this district
        cur.execute(
            "SELECT id FROM contacts WHERE district_id = %s AND role = 'superintendent'",
            (district_id,),
        )
        existing = cur.fetchone()
        if existing:
            duplicates += 1
            # Update existing record instead of skipping
            cur.execute(
                """UPDATE contacts
                   SET first_name = %s, last_name = %s, prefix = %s, suffix = %s,
                       email = %s, phone = %s, confidence_score = %s
                   WHERE id = %s""",
                (
                    rec["first_name"],
                    rec["last_name"],
                    rec["prefix"],
                    rec["suffix"],
                    rec["email"],
                    rec["phone"],
                    85,
                    existing[0],
                ),
            )
            matched += 1
            continue

        # Insert new contact
        cur.execute(
            """INSERT INTO contacts
               (district_id, role, first_name, last_name, prefix, suffix, email, phone, confidence_score)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                district_id,
                "superintendent",
                rec["first_name"],
                rec["last_name"],
                rec["prefix"],
                rec["suffix"],
                rec["email"],
                rec["phone"],
                85,
            ),
        )
        matched += 1

    conn.commit()

    print(f"\n--- Results ---")
    print(f"Total OSPI records parsed: {len(records)}")
    print(f"Matched & inserted/updated: {matched}")
    print(f"  (of which {duplicates} were updates to existing records)")
    print(f"Unmatched (no DB district found): {skipped}")

    if unmatched:
        print(f"\nUnmatched district names ({len(unmatched)}):")
        for name in sorted(unmatched):
            print(f"  - {name}")

    # Verify final count
    cur.execute(
        "SELECT COUNT(*) FROM contacts c JOIN districts d ON c.district_id = d.id WHERE d.state = 'WA' AND c.role = 'superintendent'"
    )
    total = cur.fetchone()[0]
    print(f"\nTotal WA superintendent contacts now in DB: {total}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
