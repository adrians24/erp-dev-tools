if (-not ('Codex.SqlServer.NativeCredentialManager' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

namespace Codex.SqlServer
{
    public static class NativeCredentialManager
    {
        public const UInt32 CredentialTypeGeneric = 1;
        public const UInt32 PersistLocalMachine = 2;
        public const Int32 ErrorNotFound = 1168;

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        public struct Credential
        {
            public UInt32 Flags;
            public UInt32 Type;
            [MarshalAs(UnmanagedType.LPWStr)] public string TargetName;
            [MarshalAs(UnmanagedType.LPWStr)] public string Comment;
            public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
            public UInt32 CredentialBlobSize;
            public IntPtr CredentialBlob;
            public UInt32 Persist;
            public UInt32 AttributeCount;
            public IntPtr Attributes;
            [MarshalAs(UnmanagedType.LPWStr)] public string TargetAlias;
            [MarshalAs(UnmanagedType.LPWStr)] public string UserName;
        }

        [DllImport("Advapi32.dll", EntryPoint = "CredReadW", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern bool CredRead(
            string target,
            UInt32 type,
            UInt32 reservedFlag,
            out IntPtr credentialPtr);

        [DllImport("Advapi32.dll", EntryPoint = "CredWriteW", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern bool CredWrite(ref Credential credential, UInt32 flags);

        [DllImport("Advapi32.dll", EntryPoint = "CredDeleteW", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern bool CredDelete(string target, UInt32 type, UInt32 flags);

        [DllImport("Advapi32.dll", SetLastError = false)]
        public static extern void CredFree(IntPtr credentialPtr);
    }
}
'@
}

function Get-CodexStoredCredential {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Target
    )

    $credentialPointer = [IntPtr]::Zero
    $found = [Codex.SqlServer.NativeCredentialManager]::CredRead(
        $Target,
        [Codex.SqlServer.NativeCredentialManager]::CredentialTypeGeneric,
        0,
        [ref]$credentialPointer
    )

    if (-not $found) {
        $errorCode = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        if ($errorCode -eq [Codex.SqlServer.NativeCredentialManager]::ErrorNotFound) {
            return $null
        }
        throw [ComponentModel.Win32Exception]::new($errorCode, "Unable to read Windows credential '$Target'.")
    }

    $plainTextPassword = $null
    try {
        $nativeCredential = [Runtime.InteropServices.Marshal]::PtrToStructure(
            $credentialPointer,
            [type][Codex.SqlServer.NativeCredentialManager+Credential]
        )
        if ($nativeCredential.CredentialBlobSize -gt 0) {
            $characterCount = [int]($nativeCredential.CredentialBlobSize / 2)
            $plainTextPassword = [Runtime.InteropServices.Marshal]::PtrToStringUni(
                $nativeCredential.CredentialBlob,
                $characterCount
            )
            $securePassword = ConvertTo-SecureString $plainTextPassword -AsPlainText -Force
        }
        else {
            $securePassword = New-Object Security.SecureString
        }

        return New-Object Management.Automation.PSCredential(
            $nativeCredential.UserName,
            $securePassword
        )
    }
    finally {
        $plainTextPassword = $null
        if ($credentialPointer -ne [IntPtr]::Zero) {
            [Codex.SqlServer.NativeCredentialManager]::CredFree($credentialPointer)
        }
    }
}

function Set-CodexStoredCredential {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Target,

        [Parameter(Mandatory = $true)]
        [Management.Automation.PSCredential]$Credential
    )

    $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToCoTaskMemUnicode(
        $Credential.Password
    )
    try {
        $nativeCredential = New-Object Codex.SqlServer.NativeCredentialManager+Credential
        $nativeCredential.Type = [Codex.SqlServer.NativeCredentialManager]::CredentialTypeGeneric
        $nativeCredential.TargetName = $Target
        $nativeCredential.Comment = 'Managed by the Codex sql-server skill.'
        $nativeCredential.CredentialBlobSize = [uint32]($Credential.Password.Length * 2)
        $nativeCredential.CredentialBlob = $passwordPointer
        $nativeCredential.Persist = [Codex.SqlServer.NativeCredentialManager]::PersistLocalMachine
        $nativeCredential.UserName = $Credential.UserName

        $written = [Codex.SqlServer.NativeCredentialManager]::CredWrite(
            [ref]$nativeCredential,
            0
        )
        if (-not $written) {
            $errorCode = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
            throw [ComponentModel.Win32Exception]::new($errorCode, "Unable to write Windows credential '$Target'.")
        }
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeCoTaskMemUnicode($passwordPointer)
    }
}

function Remove-CodexStoredCredential {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Target
    )

    $removed = [Codex.SqlServer.NativeCredentialManager]::CredDelete(
        $Target,
        [Codex.SqlServer.NativeCredentialManager]::CredentialTypeGeneric,
        0
    )
    if (-not $removed) {
        $errorCode = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        if ($errorCode -ne [Codex.SqlServer.NativeCredentialManager]::ErrorNotFound) {
            throw [ComponentModel.Win32Exception]::new($errorCode, "Unable to remove Windows credential '$Target'.")
        }
    }
}
