%global debug_package %{nil}

%{!?version_override:%global version_override 1.0.01}
Name:           mishkah-note
Version:        %{version_override}
Release:        1%{?dist}
Summary:        Windows 11-style text editor with first-class Arabic, RTL and Markdown support

License:        MIT
URL:            https://github.com/bifa90/Mishkah-Note
Source0:        Mishkah-Note-%{version}.tar.gz
BuildArch:      noarch

Requires:       python3 >= 3.9
Requires:       (python3-pyside6 or python3dist(pyside6))
Requires:       (python3-charset-normalizer or python3dist(charset-normalizer))
Recommends:     (google-noto-sans-fonts or noto-sans-fonts)
Recommends:     (google-noto-sans-arabic-fonts or noto-sans-arabic-fonts)
Recommends:     (liberation-fonts or liberation-sans-fonts)

%description
A fast, minimal text editor for the Linux desktop, styled after the Windows 11
Notepad.  The writing direction is resolved per document — automatically from
the content, or explicitly right-to-left / left-to-right — instead of being
forced globally, so Arabic and English files each render correctly.  It
auto-closes brackets, indents intelligently, offers optional syntax
highlighting and word completion, colours and pins tabs, ships an Arabic
typeface, speaks ten languages, and opens very large files in chunks.

%prep
%setup -q -n Mishkah-Note-%{version}

%build
# Python sources are installed directly; no wheel or network is needed.

%install
rm -rf %{buildroot}
install -d %{buildroot}%{_libexecdir}/mishkah-note
cp -r src/mishkah %{buildroot}%{_libexecdir}/mishkah-note/
find %{buildroot}%{_libexecdir} -name '__pycache__' -type d -prune -exec rm -rf {} +

install -d %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/mishkah <<'EOF'
#!/bin/sh
PYTHONPATH=%{_libexecdir}/mishkah-note${PYTHONPATH:+:$PYTHONPATH} exec python3 -m mishkah "$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/mishkah

install -d %{buildroot}%{_datadir}/applications
install -m644 packaging/common/mishkah.desktop \
    %{buildroot}%{_datadir}/applications/mishkah-note.desktop

install -d %{buildroot}%{_datadir}/metainfo
install -m644 packaging/common/org.mishkahnote.Mishkah.metainfo.xml \
    %{buildroot}%{_datadir}/metainfo/org.mishkahnote.Mishkah.metainfo.xml

for size in 16 24 32 48 64 128 256 512; do
    install -Dm644 "src/mishkah/resources/icons/app-${size}.png" \
        "%{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/apps/mishkah-note.png"
done
install -Dm644 src/mishkah/resources/icons/app.svg \
    "%{buildroot}%{_datadir}/icons/hicolor/scalable/apps/mishkah-note.svg"

install -d %{buildroot}%{_mandir}/man1
install -m644 packaging/common/mishkah.1 %{buildroot}%{_mandir}/man1/mishkah.1

%files
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/mishkah
%{_libexecdir}/mishkah-note
%{_datadir}/applications/mishkah-note.desktop
%{_datadir}/metainfo/org.mishkahnote.Mishkah.metainfo.xml
%{_datadir}/icons/hicolor/*/apps/mishkah-note.png
%{_datadir}/icons/hicolor/scalable/apps/mishkah-note.svg
%{_mandir}/man1/mishkah.1*

%changelog
* Thu Oct 22 2026 Mishkah-Note contributors <noreply@github.com> - 1.0.01-1
- First release of Mishkah Note.
- Live Markdown view (opt-in) that never changes the file.
- Auto-pairing, smart indentation and word completion.
- Optional syntax highlighting for sixteen languages.
- Coloured and pinnable tabs; per-document text direction; large-file pipeline.
