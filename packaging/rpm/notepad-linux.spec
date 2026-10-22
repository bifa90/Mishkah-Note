%global debug_package %{nil}

%{!?version_override:%global version_override 1.0.01}
Name:           notepad-linux
Version:        %{version_override}
Release:        1%{?dist}
Summary:        Windows 11-style text editor with first-class Arabic, RTL and Markdown support

License:        MIT
URL:            https://github.com/bifa90/Notepad-Linux
Source0:        Notepad-Linux-%{version}.tar.gz
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
%setup -q -n Notepad-Linux-%{version}

%build
# No network during %build: a plain wheel from the checkout.
%{__python3} -m build --wheel --no-isolation 2>/dev/null || \
    %{__python3} setup.py bdist_wheel 2>/dev/null || true

%install
rm -rf %{buildroot}
install -d %{buildroot}%{_libexecdir}/notepad-linux
cp -r src/mufakkira %{buildroot}%{_libexecdir}/notepad-linux/
find %{buildroot}%{_libexecdir} -name '__pycache__' -type d -prune -exec rm -rf {} +

install -d %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/notepad <<'EOF'
#!/bin/sh
PYTHONPATH=%{_libexecdir}/notepad-linux${PYTHONPATH:+:$PYTHONPATH} exec python3 -m mufakkira "$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/notepad

install -d %{buildroot}%{_datadir}/applications
install -m644 packaging/common/notepad.desktop \
    %{buildroot}%{_datadir}/applications/notepad-linux.desktop

install -d %{buildroot}%{_datadir}/metainfo
install -m644 packaging/common/org.notepadlinux.Notepad.metainfo.xml \
    %{buildroot}%{_datadir}/metainfo/org.notepadlinux.Notepad.metainfo.xml

for size in 16 24 32 48 64 128 256 512; do
    install -Dm644 "src/mufakkira/resources/icons/app-${size}.png" \
        "%{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/apps/notepad-linux.png"
done
install -Dm644 src/mufakkira/resources/icons/app.svg \
    "%{buildroot}%{_datadir}/icons/hicolor/scalable/apps/notepad-linux.svg"

install -d %{buildroot}%{_mandir}/man1
install -m644 packaging/common/notepad.1 %{buildroot}%{_mandir}/man1/notepad.1

%files
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/notepad
%{_libexecdir}/notepad-linux
%{_datadir}/applications/notepad-linux.desktop
%{_datadir}/metainfo/org.notepadlinux.Notepad.metainfo.xml
%{_datadir}/icons/hicolor/*/apps/notepad-linux.png
%{_datadir}/icons/hicolor/scalable/apps/notepad-linux.svg
%{_mandir}/man1/notepad.1*

%changelog
* Wed Oct 22 2026 Notepad-Linux contributors <noreply@github.com> - 1.0.01-1
- First public release of the rebuilt editor.
- Live Markdown view (opt-in) that never changes the file.
- Auto-pairing, smart indentation and word completion.
- Optional syntax highlighting for fourteen languages.
- Coloured and pinnable tabs; per-document text direction; large-file pipeline.
