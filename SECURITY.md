# Security and authorized use

TSK | The Skeleton Key is a **security research and education tool** for building and deploying USB / HID payloads in **controlled lab environments**.

## Authorized use only

You may use TSK **only** when **all** of the following are true:

- You own the systems and networks involved, **or**
- You have **written, prior authorization** from the system owner to perform security testing in that environment.

**Permitted examples**

- Your home lab, VMs, and test machines you control
- A corporate or client engagement with a signed scope of work and explicit permission
- CTF, training, or research environments where deployment is allowed by the rules

**Not permitted**

- Deploying against systems, accounts, or networks you do not own or lack permission to test
- Harassment, fraud, theft, or any activity that violates applicable law
- Using TSK to harm people or organizations without authorization

If you are unsure whether you are allowed to test, **do not deploy**. Get permission first.

## Disclaimer

TSK is provided **as is**, without warranty. The authors and contributors are **not responsible** for misuse, illegal activity, or damage arising from your use of this software.

You are solely responsible for complying with laws and policies that apply to you. The "Hack the Planet" easter egg and similar UI flourishes are **fiction and nostalgia** - not an invitation to break the law.

## Reporting security vulnerabilities

If you find a **security vulnerability in TSK itself** (not a feature working as designed for authorized lab use):

1. **Do not** open a public GitHub issue for exploitable details until we have had a reasonable chance to respond.
2. Email **[neur0sp1cy@proton.me](mailto:neur0sp1cy@proton.me)** or open a [GitHub Discussion / profile message](https://github.com/neur0sp1cy) with:
   - Description of the issue
   - Steps to reproduce in an authorized lab
   - Impact assessment
   - Your environment (TSK version / commit, OS, Python version)
3. Allow a reasonable time for a fix before public disclosure.

For **general bugs** (UI glitches, flash failures, doc errors), use [GitHub Issues](https://github.com/neur0sp1cy/TSK2/issues) and include repro steps from [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md).

For **questions or concerns** (non-security): [neur0sp1cy@proton.me](mailto:neur0sp1cy@proton.me).

## Sensitive data in your checkout

Never commit operator data or TLS private keys. These paths are gitignored:

- `users/` (operator accounts, configs, saved payloads)
- `snarfed/` (phone-home catches)
- `ssl/` (generated certificates)
- `.env`

If you accidentally commit secrets, rotate credentials and remove them from git history before pushing.

## Support expectations

- **Best-effort** open source support via GitHub Issues
- Be constructive; abusive behavior may be ignored or blocked
- Include checklist section, OS, and repro steps to help us help you

See [README.md](README.md) for install and lab setup.
