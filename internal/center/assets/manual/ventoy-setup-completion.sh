# Sourced by Bash for interactive logins.
[ -n "${BASH_VERSION-}" ] || return 0
case $- in
    *i*) if [ -r /usr/share/ventoy-setup/ventoy-setup-completion.bash ]; then
             . /usr/share/ventoy-setup/ventoy-setup-completion.bash
         fi;;
esac
