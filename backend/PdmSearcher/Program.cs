using System;
using System.Reflection;
using System.Runtime.InteropServices;

namespace PdmSearcher
{
    class Program
    {
        static void Main(string[] args)
        {
            // Set encoding to handle Turkish characters
            Console.OutputEncoding = System.Text.Encoding.UTF8;

            if (args.Length == 0) return;
            string sapCode = args[0];
            string vaultName = "PGR2024";

            try
            {
                Type vaultType = Type.GetTypeFromProgID("ConisioLib.EdmVault5");
                if (vaultType == null) vaultType = Type.GetTypeFromProgID("ConisioLib.EdmVault");
                
                if (vaultType == null) return;

                dynamic vault = Activator.CreateInstance(vaultType);
                
                bool isLoggedIn = false;
                try { isLoggedIn = vault.IsLoggedIn; } catch {}
                
                if (!isLoggedIn)
                {
                    vault.LoginAuto(vaultName, 0);
                }

                string[] varNames = { "SAP Numarası", "SAP Numarasi", "SAP No", "SAP NO" };

                // 1. Variable Search
                foreach (string varName in varNames)
                {
                    try
                    {
                        dynamic search = vault.CreateSearch();
                        search.AddVariable(varName, sapCode);
                        
                        dynamic result = search.GetFirstResult();
                        while (result != null)
                        {
                            try
                            {
                                int fileId = result.ID;
                                if (CheckFileVariable(vault, fileId, varNames, sapCode))
                                {
                                    Console.WriteLine(result.Path);
                                    return;
                                }
                            }
                            catch { }
                            result = search.GetNextResult();
                        }
                    }
                    catch { }
                }

                // 2. Filename Search (Fallback with strict check)
                try
                {
                    dynamic fileSearch = vault.CreateSearch();
                    fileSearch.FileName = "%" + sapCode + "%";
                    
                    dynamic fResult = fileSearch.GetFirstResult();
                    while (fResult != null)
                    {
                        try
                        {
                            int fileId = fResult.ID;
                            if (CheckFileVariable(vault, fileId, varNames, sapCode))
                            {
                                Console.WriteLine(fResult.Path);
                                return;
                            }
                        }
                        catch { }
                        fResult = fileSearch.GetNextResult();
                    }
                }
                catch { }
            }
            catch (Exception ex) 
            {
                Console.Error.WriteLine("Critical error: " + ex.Message);
            }
        }

        static bool CheckFileVariable(dynamic vault, int fileId, string[] varNames, string targetCode)
        {
            try
            {
                // EdmObjectType.EdmObject_File = 1
                dynamic file = vault.GetObject(1, fileId);
                
                if (file != null)
                {
                    string fileName = file.Name;
                    string ext = System.IO.Path.GetExtension(fileName).ToLower();
                    if (ext != ".sldprt" && ext != ".sldasm") return false;

                    dynamic varEnum = file.GetEnumeratorVariable();
                    
                    // Check @ tab
                    foreach (string varName in varNames)
                    {
                        object val = null;
                        if (varEnum.GetVar(varName, "@", out val) && val != null)
                        {
                            string sVal = val.ToString().Trim();
                            if (sVal == targetCode.Trim()) return true;
                        }
                    }
                }
            }
            catch { }
            return false;
        }
    }
}
