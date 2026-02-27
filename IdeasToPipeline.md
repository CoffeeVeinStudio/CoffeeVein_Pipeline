Bugs.
    shot manager
        Importing av bildsekvenser sätter inte colorspace
        klickar man på Refresh knappen hoppas man till reference gruppen. stanna där man är. Altså den gruppen man kollar på.
        nu när man packar externa plates och väljer att flytta dem till skottet hamnar dem automatiskt i plates. jag vill kunna välja om det är en plate, 3D eller ref.
        nu när man flyttar många filer via packagern så slutar den svara till alla är flyttade. kör en progressbar istället.

feature to shot manager.
    - I need to be able to add common plates. Like if i use a texture in multiople shots. I need to be able to easaly add this to each and every shot. could we create a ned category like _incoming and reference that is shared plates?
    - Apply TIK settings ändrar bara fps och fomrat. inte framerangen.
    - add a "open packaged project" button in the UI.
    - Justera de readnoder som går till att ha relativa sökvägar. (Ändra också "project_directory" knoben i rooten till "[python {nuke.script_directory()}]")
    - Byta namn på ett skott och rendering. A001_C005 -> A_0001C005 till exempel

feature to TIK
    - om nuke.allNodes() bara innehåller viewern, [<Viewer1 at 0x0000023DF6CCDA70>] och om nuke.root().name() är Root. fråga inte om jag vill spara. det finns inget i scriptet


New tools:
    Panel med paneler i nuke.
        jag gillar min setup på vänstra sidan.
            moitor out
            error consol
            script editorn
            Waveform/pixel analyz   Histogram   vectorscope
        men jag skulle på ett enkelt sätt kunna flippa till en annan vy, utan att ladda ett nytt workspace
            TIK manager
            Shot Manager