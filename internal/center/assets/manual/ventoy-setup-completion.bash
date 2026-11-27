_ventoy_setup_complete() {
    local current=${COMP_WORDS[COMP_CWORD]} previous=${COMP_WORDS[COMP_CWORD-1]}
    local mode= word options
    COMPREPLY=()
    case "$previous" in
        --hostname) return 0;;
        --login-user) mapfile -t COMPREPLY < <(compgen -u -- "$current"); return 0;;
    esac
    for word in "${COMP_WORDS[@]:1:COMP_CWORD-1}"; do
        case "$word" in
            --apply|--upgrade|--uninstall|--restore-user-login|--check|--offline|--hostname|--keep-passwords|--software|--list-software|--check-software|--install-fyhoct|--check-login|--version|--check-version|--update-setup|--help|-h|help)
                mode=$word; break;;
        esac
    done
    case "$mode" in
        '') options='--apply --hostname --offline --keep-passwords --check --list-software --software --check-software --install-fyhoct --restore-user-login --check-login --version --check-version --update-setup --upgrade --uninstall --help -h help';;
        --apply|--hostname|--offline|--keep-passwords) options='--hostname --offline --keep-passwords';;
        --upgrade) options='--hostname --keep-passwords';;
        --uninstall) options='--login-user --include-legacy-packages';;
        --restore-user-login) options='--login-user';;
        *) return 0;;
    esac
    mapfile -t COMPREPLY < <(compgen -W "$options" -- "$current")
}
complete -F _ventoy_setup_complete ventoy-linux-setup.run
