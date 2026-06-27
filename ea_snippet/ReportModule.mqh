//+------------------------------------------------------------------+
//|                                              ReportModule.mqh     |
//|  MIDAS Gold AI EA — Module tu bao cao trang thai tai khoan        |
//|  ve Report Server trung tam (de Server day tiep qua Telegram).    |
//|                                                                    |
//|  Cach dung trong EA chinh:                                        |
//|    #include <ReportModule.mqh>                                    |
//|    int OnInit() { ... ReportInit(); ... }                         |
//|    void OnTimer() { ... ReportSendSnapshot(...); ... }            |
//|                                                                    |
//|  YEU CAU: Trong MT5 > Tools > Options > Expert Advisors,           |
//|  them URL server vao danh sach "Allow WebRequest for listed URL". |
//+------------------------------------------------------------------+
#property strict

input string Report_ServerURL   = "https://your-report-server.example.com/api/report";
input string Report_ApiKey      = "CHANGE_ME_SECRET_KEY";   // dung de Server xac thuc request tu EA
input string Report_PresetName  = "Master Alpha";            // "Master Alpha" | "Master Elite" | ten preset tuy chinh
input int    Report_IntervalSec = 60;                        // tan suat gui bao cao (giay)

datetime g_lastReportTime = 0;

//--- Goi 1 lan trong OnInit() cua EA chinh
void ReportInit()
  {
   g_lastReportTime = 0;
  }

//--- Helper: dem so lenh dang mo + tong lot cua symbol hien tai, tach Buy/Sell
void ReportGetOrderStats(string symbol, int &totalOrders, int &buyOrders, int &sellOrders,
                          double &totalLots, double &buyLots, double &sellLots)
  {
   totalOrders = 0; buyOrders = 0; sellOrders = 0;
   totalLots = 0; buyLots = 0; sellLots = 0;

   for(int i = 0; i < PositionsTotal(); i++)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != symbol) continue;

      double vol = PositionGetDouble(POSITION_VOLUME);
      long   type = PositionGetInteger(POSITION_TYPE);

      totalOrders++;
      totalLots += vol;
      if(type == POSITION_TYPE_BUY) { buyOrders++; buyLots += vol; }
      else                          { sellOrders++; sellLots += vol; }
     }
  }

//--- Phan loai "suc khoe bo lenh" theo nguong trong tai lieu van hanh
//    < 15 lenh: AN TOAN | 15-25: QUAN SAT (AI co the nang lot) | >= 26: NGUY HIEM (gan/dang Hedge)
string ReportHealthStatus(int totalOrders, bool hedgeActive)
  {
   if(hedgeActive)        return "HEDGE_LOCKED";
   if(totalOrders >= 26)  return "CRITICAL";
   if(totalOrders >= 15)  return "WATCH";
   return "SAFE";
  }

//--- Goi dinh ky (vi du trong OnTimer, EA dat EventSetTimer(Report_IntervalSec))
//    hedgeActive, loopActive, aiConfidence, licenseExpiry: lay tu bien noi bo cua EA
void ReportSendSnapshot(string symbol, bool loopActive, bool hedgeActive,
                         double aiConfidence, datetime licenseExpiry,
                         double zonePoints, double tpPoints, double multiplier, int maxOrders)
  {
   datetime now = TimeCurrent();
   if(now - g_lastReportTime < Report_IntervalSec) return;
   g_lastReportTime = now;

   int totalOrders, buyOrders, sellOrders;
   double totalLots, buyLots, sellLots;
   ReportGetOrderStats(symbol, totalOrders, buyOrders, sellOrders, totalLots, buyLots, sellLots);

   double balance     = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity      = AccountInfoDouble(ACCOUNT_EQUITY);
   double marginLevel = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   double floatingPL  = equity - balance;
   double drawdownPct = (balance > 0) ? (balance - equity) / balance * 100.0 : 0.0;
   long   login        = AccountInfoInteger(ACCOUNT_LOGIN);
   string server        = AccountInfoString(ACCOUNT_SERVER);
   string accCurrency   = AccountInfoString(ACCOUNT_CURRENCY);
   bool   isCent         = (StringFind(accCurrency, "Cent") >= 0 || StringFind(server, "Cent") >= 0);

   string health = ReportHealthStatus(totalOrders, hedgeActive);

   // Lay volume da khop trong ngay (deal history) de phuc vu bao cao Volume/IB
   double closedLotsToday = ReportGetClosedLotsToday(symbol);

   string json = StringFormat(
      "{"
      "\"api_key\":\"%s\","
      "\"login\":%I64d,"
      "\"server\":\"%s\","
      "\"symbol\":\"%s\","
      "\"preset\":\"%s\","
      "\"is_cent\":%s,"
      "\"balance\":%.2f,"
      "\"equity\":%.2f,"
      "\"margin_level\":%.2f,"
      "\"floating_pl\":%.2f,"
      "\"drawdown_pct\":%.2f,"
      "\"total_orders\":%d,"
      "\"buy_orders\":%d,"
      "\"sell_orders\":%d,"
      "\"total_lots\":%.2f,"
      "\"closed_lots_today\":%.2f,"
      "\"loop_active\":%s,"
      "\"hedge_active\":%s,"
      "\"ai_confidence\":%.1f,"
      "\"zone_points\":%.1f,"
      "\"tp_points\":%.1f,"
      "\"multiplier\":%.2f,"
      "\"max_orders\":%d,"
      "\"health_status\":\"%s\","
      "\"license_expiry\":\"%s\","
      "\"timestamp\":\"%s\""
      "}",
      Report_ApiKey, login, server, symbol, Report_PresetName,
      isCent ? "true" : "false",
      balance, equity, marginLevel, floatingPL, drawdownPct,
      totalOrders, buyOrders, sellOrders, totalLots, closedLotsToday,
      loopActive ? "true" : "false", hedgeActive ? "true" : "false",
      aiConfidence, zonePoints, tpPoints, multiplier, maxOrders,
      health,
      TimeToString(licenseExpiry, TIME_DATE),
      TimeToString(now, TIME_DATE | TIME_SECONDS)
   );

   char post[]; char result[]; string headers;
   StringToCharArray(json, post, 0, StringLen(json));
   ResetLastError();
   int res = WebRequest("POST", Report_ServerURL, "Content-Type: application/json\r\n", 5000,
                         post, result, headers);
   if(res == -1)
      Print("[ReportModule] WebRequest loi: ", GetLastError(), " - kiem tra URL da duoc whitelist trong Options > Expert Advisors");
  }

//--- Tinh tong lot da khop (deals) trong ngay hien tai cho symbol, dung cho bao cao Volume/IB
double ReportGetClosedLotsToday(string symbol)
  {
   double sumLots = 0;
   datetime dayStart = TimeCurrent() - (TimeCurrent() % 86400);
   if(!HistorySelect(dayStart, TimeCurrent())) return 0;

   int deals = HistoryDealsTotal();
   for(int i = 0; i < deals; i++)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket <= 0) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != symbol) continue;
      if(HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue; // chi tinh lenh da dong
      sumLots += HistoryDealGetDouble(ticket, DEAL_VOLUME);
     }
   return sumLots;
  }
//+------------------------------------------------------------------+
