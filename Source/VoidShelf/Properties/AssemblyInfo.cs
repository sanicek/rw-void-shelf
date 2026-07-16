using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;

// The project disables SDK-generated assembly attributes so the identity of the
// recovered mod remains explicit and reviewable in one place.
[assembly: AssemblyTitle("VoidShelf")]
[assembly: AssemblyDescription("")]
[assembly: AssemblyConfiguration("")]
[assembly: AssemblyCompany("")]
[assembly: AssemblyProduct("VoidShelf")]
[assembly: AssemblyCopyright("Copyright ©  2023")]
[assembly: AssemblyTrademark("")]
[assembly: AssemblyCulture("")]

// RimWorld loads the assembly through managed reflection; exposing its types to
// COM would add an unrelated integration surface.
[assembly: ComVisible(false)]

// Retain the recovered COM type-library GUID as stable assembly metadata even
// though COM exposure is disabled.
[assembly: Guid("4897cec7-0b6b-49f6-93ff-147f61c35631")]

// Runtime compatibility is selected by LoadFolders.xml, not assembly-version
// probing. Keep this identity stable unless a deliberate binary compatibility
// change requires a new assembly version.
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]
