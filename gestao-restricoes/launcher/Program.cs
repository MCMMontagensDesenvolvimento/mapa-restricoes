using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Text.RegularExpressions;
using System.Windows.Forms;
static class Program {
 [STAThread] static void Main(){
  try{
   var path=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"LeanControl.Launcher.json");
   var json=File.ReadAllText(path);
   var url=Value(json,"url"); var health=Value(json,"healthUrl");
   var request=(HttpWebRequest)WebRequest.Create(health);request.Timeout=10000;request.Method="GET";
   using(var response=(HttpWebResponse)request.GetResponse()){if((int)response.StatusCode>=400)throw new Exception("O serviço Lean Control está indisponível.");}
   Process.Start(new ProcessStartInfo(url){UseShellExecute=true});
  }catch(Exception ex){MessageBox.Show(ex.Message,"Lean Control",MessageBoxButtons.OK,MessageBoxIcon.Warning);}
 }
 static string Value(string json,string key){var m=Regex.Match(json,"\\\""+key+"\\\"\\s*:\\s*\\\"([^\\\"]+)\\\"");if(!m.Success)throw new Exception("Configuração do launcher inválida.");return m.Groups[1].Value;}
}
