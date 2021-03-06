import fontforge
import os
import subprocess
import tempfile
import json

#
# Manifest / Options
# Older Pythons don't have argparse, so we use optparse instead
#

try:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', help='Path to .fontcustom-manifest.json')
    args = parser.parse_args()
    manifestfile = open(args.manifest, 'r+')
except ImportError:
    import optparse
    parser = optparse.OptionParser()
    (nothing, args) = parser.parse_args()
    manifestfile = open(args[0], 'r+')

manifest = json.load(manifestfile)
options = manifest['options']
gempath = manifest['gem_path']
blankpath = gempath + "/scripts/blank.svg"

print "gem path is", gempath

#
# Font
#

font = fontforge.font()
font.encoding = 'UnicodeFull'
font.design_size = 16
font.em = 512
font.ascent = 448
font.descent = 64
font.fontname = options['font_name']
font.familyname = options['font_name']
font.fullname = options['font_name']
if options['autowidth']:
    font.autoWidth(0, 0, 512)

# NOTE not referenced anywhere, safe to remove?
KERNING = 15

#
# Init ligature table
#

font.addLookup("ligatable","gsub_ligature",(),(("liga",(("latn",("dflt")),)),))
font.addLookupSubtable("ligatable","ligatable1")
print "add lookup table"

#
# Create base ASCII glyphs
#

for code in range(0,256):
    glyph = font.createChar(code)
    glyph.importOutlines(blankpath)
    glyph.width = 512
print "creates base glyphs"

#
# Glyphs
#

def removeSwitchFromSvg( file ):
    svgfile = open(file, 'r+')
    tmpsvgfile = tempfile.NamedTemporaryFile(suffix=".svg", delete=False)
    svgtext = svgfile.read()
    svgfile.seek(0)
    svgtext = svgtext.replace('<switch>', '')
    svgtext = svgtext.replace('</switch>', '')
    tmpsvgfile.file.write(svgtext)
    svgfile.close()
    tmpsvgfile.file.close()

    return tmpsvgfile.name

def glyphName( c ):
    if c == "-":
        #c = "hyphen(-)"
        c = None
    elif c == "_":
        #c = "under(_)"
        c = None
    elif c == "0":
        c = "zero(0)"
    elif c == "1":
        c = "one(1)"
    elif c == "2":
        c = "two(2)"
    elif c == "3":
        c = "three(3)"
    elif c == "4":
        c = "four(4)"
    elif c == "5":
        c = "five(5)"
    elif c == "6":
        c = "six(6)"
    elif c == "7":
        c = "seven(7)"
    elif c == "8":
        c = "height(8)"
    elif c == "9":
        c = "nine(9)"

    return c;

def createGlyph( name, source, code ):
    frag, ext = os.path.splitext(source)

    if ext == '.svg':
        temp = removeSwitchFromSvg(source)
        glyph = font.createChar(code)
        glyph.importOutlines(temp)
        os.unlink(temp)

        if options['autowidth']:
            glyph.left_side_bearing = glyph.right_side_bearing = 0
            glyph.round()
        else:
            glyph.width = 512

        # add ligature
        ligature = []
        for c in name:
            c = glyphName(c)
            if c is not None:
                ligature.append(c)
        glyph.addPosSub("ligatable1",ligature)
        print "add ligature \"" + (" ".join(ligature)) + "\""

for glyph in sorted(manifest['glyphs'], reverse=True):
    data = manifest['glyphs'][glyph]
    name = createGlyph(glyph, data['source'], data['codepoint'])

#
# Generate Files
#

try:
    fontfile = options['output']['fonts'] + '/' + options['font_name']
    if not options['no_hash']:
        fontfile += '_' + manifest['checksum']['current'][:32]

    # Generate TTF and SVG
    font.generate(fontfile + '.ttf')
    font.generate(fontfile + '.svg')
    manifest['fonts'].append(fontfile + '.ttf')
    manifest['fonts'].append(fontfile + '.svg')

    # Fix SVG header for webkit
    # from: https://github.com/fontello/font-builder/blob/master/bin/fontconvert.py
    svgfile = open(fontfile + '.svg', 'r+')
    svgtext = svgfile.read()
    svgfile.seek(0)
    svgfile.write(svgtext.replace('''<svg>''', '''<svg xmlns="http://www.w3.org/2000/svg">'''))
    svgfile.close()

    # Convert WOFF
    scriptPath = os.path.dirname(os.path.realpath(__file__))
    try:
        subprocess.Popen([scriptPath + '/sfnt2woff', fontfile + '.ttf'], stdout=subprocess.PIPE)
    except OSError:
        # If the local version of sfnt2woff fails (i.e., on Linux), try to use the
        # global version. This allows us to avoid forcing OS X users to compile
        # sfnt2woff from source, simplifying install.
        subprocess.call(['sfnt2woff', fontfile + '.ttf'])
    manifest['fonts'].append(fontfile + '.woff')

    # Convert EOT for IE7
    subprocess.call('python ' + scriptPath + '/eotlitetool.py ' + fontfile + '.ttf -o ' + fontfile + '.eot', shell=True)
    subprocess.call('mv ' + fontfile + '.eotlite ' + fontfile + '.eot', shell=True)
    manifest['fonts'].append(fontfile + '.eot')

finally:
    manifestfile.seek(0)
    manifestfile.write(json.dumps(manifest, indent=2, sort_keys=True))
    manifestfile.truncate()
    manifestfile.close()
