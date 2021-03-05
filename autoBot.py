import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QAxContainer import *
from PyQt5 import uic
import time

form_class = uic.loadUiType("autoBot.ui")[0]


class autoBot(QMainWindow, form_class):
    current_jango_list = {}
    current_cond_list = []
    account = ""
    current_cond_num = ""
    current_cond_name = ""

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.current_jango_list = {}
        self.current_cond_list = []
        self.account = ""
        self.current_cond_num = ""
        self.current_cond_name = ""

        # 키움api 위젯 객체 생성, 이벤트 슬롯 등록, 로그인 이벤트 진행, 조건식 로컬에 저장
        self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self._set_signal_slots()
        self.comm_connect()
        self.get_condition_load()

        self.event_log.append("autoBot Ver 0.1 - Beta")

        # 계좌 관련 정보 받아오기
        accounts_num = int(self.get_login_info("ACCOUNT_CNT"))
        accounts = self.get_login_info("ACCNO")
        accounts_list = accounts.split(';')[0:accounts_num]
        self.account = accounts_list[0]
        self.event_log.append("계좌번호 : " + self.account)

        # 전일 거래량 상위 10개 로컬 저장 후, 구매.
        self.set_input_value("시장구분", "000")
        self.set_input_value("조회구분", "1")
        self.set_input_value("순위시작", "0")
        self.set_input_value("순위끝", "10")
        self.comm_rq_data("opt10031_req", "opt10031", 0, "0001")

        f = open("lastday_top10.txt", "r")
        read = f.readlines()
        for item in read:
            errcode = self.send_order("send_order_req", "0002",
                                      self.account, 1, item[:-1], 1, 0, "03", "")
            print("에러코드 : ", errcode, "구매종목 : ", item[:-1])
            time.sleep(0.5)
        f.close()

        # 조건관련
        cond = self.kiwoom.dynamicCall("GetConditionNameList")
        cond_list = cond.split(';')[:-1]
        self.cond_combo.addItems(cond_list)

        # 잔고 데이터 저장
        self.get_jango()
        print(self.current_jango_list)

        self.start_btn.clicked.connect(self.start_trade)

    def start_trade(self):
        cond_split = self.cond_combo.currentText().split('^')
        self.current_cond_num = cond_split[0]
        self.current_cond_name = cond_split[1]
        self.send_condition("0001", self.current_cond_name,
                            self.current_cond_num, 1)
        print("실시간 종목 : ")
        print(self.current_cond_list)
        if self.current_cond_list:
            for item in self.current_cond_list:
                if item in self.current_jango_list.keys():
                    pass
                else:
                    self.send_order("실시간 매수", "0003", self.account,
                                    1, item, 1, "", "03", "")
                    self.current_jango_list[item] = self.get_master_code_name(
                        item)
                    time.sleep(0.5)

    def get_jango(self):
        password = self.password_line.text()

        self.set_input_value("계좌번호", self.account)
        self.set_input_value("비밀번호", password)
        self.set_input_value("비밀번호입력매체구분", "00")
        self.set_input_value("조회구분", "1")
        self.comm_rq_data("opw00018_req", "opw00018", 0, "2000")

    def _set_signal_slots(self):
        self.kiwoom.OnEventConnect.connect(self._event_connect)
        self.kiwoom.OnReceiveTrData.connect(self._receive_tr_data)
        self.kiwoom.OnReceiveConditionVer.connect(self._cond_get_event)
        self.kiwoom.OnReceiveTrCondition.connect(self._receive_cond_tr_data)
        self.kiwoom.OnReceiveRealCondition.connect(self._receive_real_cond)
        self.kiwoom.OnReceiveChejanData.connect(self._receive_chejan_data)
        self.kiwoom.OnReceiveMsg.connect(self._receive_msg)

    def _event_connect(self, err_code):
        if err_code == 0:
            self.event_log.append("connected")
        else:
            self.event_log.append("disconnected")

        self.login_event_loop.exit()

    def _cond_get_event(self, err_code):
        if err_code == 1:
            self.event_log.append("success to get cond to local")
        else:
            self.event_log.append("failed to get cond to local")

        self.get_condition_loop.exit()

    def _get_comm_data(self, trcode, record_name, index, item_name):
        data = self.kiwoom.dynamicCall("GetCommData(QString, Qstring, int, Qstring",
                                       trcode, record_name, index, item_name)
        return data.strip()

    def _get_comm_real_data(self, code_num, fid):
        data = self.kiwoom.dynamicCall(
            "GetCommRealData(Qstring, int)", code_num, fid)
        return data.strip()

    def _get_repeat_cnt(self, trcode, rqname):
        count = self.kiwoom.dynamicCall(
            "GetRepeatCnt(QString, QString)", trcode, rqname)
        return count

    def _receive_tr_data(self, screen_no, rqname, trcode, record_name, next, unused1, unused2, unused3, unused4):
        if next == '2':
            self.remained_data = True
        else:
            self.remained_data = False

        if trcode == "opw00018":
            self._opw00018(rqname, trcode)
        elif trcode == "opt10031":
            self._opt10031(rqname, trcode)

        try:
            self.tr_event_loop.exit()
        except AttributeError:
            pass

    def _receive_cond_tr_data(self, item_num, item_list, cond_num, cond_name, search):
        self.current_cond_list = item_list.split(';')[:-1]
        self.event_log.append("current_tmp_list : ")
        print(self.current_cond_list)
        self.get_cond_item_loop.exit()

        # for item in self.cond_itemlist:
        #     print(self.kiwoom.dynamicCall("GetMasterCodeName(QString)", item))

    # future work : send_order에 들어가는 변수 정리.
    def _receive_real_cond(self, item_code, event_type, cond_name, cond_num):
        current_time = QTime.currentTime()
        text_time = current_time.toString("hh:mm:ss")
        time_msg = "[" + text_time + "]"
        name = self.get_master_code_name(item_code)
        if event_type == "I":
            msg = time_msg + " 편입 : " + name
            self.event_log.append(msg)
            # future work : send_order에 들어가는 변수 정리.
            # 구매 전, 이미 가지고 있는지 체크.
            if item_code in self.current_jango_list.keys():
                pass
            else:
                self.send_order("실시간 편입 매수", "0004", self.account,
                                1, item_code, 1, "", "03", "")
                self.event_log.append(item_code + " 매수 신청")

        else:
            msg = time_msg + " 이탈 : " + name
            print(msg)
            self.event_log.append(msg)

    def _receive_msg(self, screen_num, rqname, trcode, msg):
        log = "order msg : " + rqname + " / " + msg
        self.event_log.append(log)

    def _receive_chejan_data(self, gubun, item_cnt, fid_list):
        if gubun == 0:
            log = "[주문 체결] 주문번호 : " + \
                self.get_chejan_data(9203) + ", 종목 : " + \
                self.get_chejan_data(9001)
            self.event_log.append(log)
        elif gubun == 1:
            name = self.get_chejan_data(9001)
            log = "[잔고 변경] 종목 추가 : " + name
            self.event_log.append(log)
            self.get_jango()

        else:
            pass

    def _opw00018(self, rqname, trcode):
        cnt = self._get_repeat_cnt(trcode, rqname)

        for i in range(cnt):
            item = self._get_comm_data(trcode, rqname, i, "종목명")
            code = self._get_comm_data(trcode, rqname, i, "종목번호")
            if len(code) > 6:
                code = code[1:]
            print(item, " ", code)
            self.current_jango_list[code] = item

    def _opt10031(self, rqname, trcode):
        cnt = self._get_repeat_cnt(trcode, rqname)
        f = open("lastday_top10.txt", "w")
        for i in range(0, cnt):
            item = self._get_comm_data(trcode, rqname, i, "종목코드")
            # print(self._get_comm_data(trcode, rqname, i, "종목명"))
            f.write(item)
            f.write("\n")
        f.close()
        self.event_log.append("전일 거래량 순위 10위 저장 완료 - lastday_top10.txt")
        self.tr_event_loop.exit()

    def get_login_info(self, tag):
        ret = self.kiwoom.dynamicCall("GetLoginInfo(QString)", tag)
        return ret

    # for login sequence
    def comm_connect(self):
        self.kiwoom.dynamicCall("CommConnect()")
        self.login_event_loop = QEventLoop()
        self.login_event_loop.exec_()

    def get_condition_load(self):
        self.kiwoom.dynamicCall("getConditionLoad()")
        self.get_condition_loop = QEventLoop()
        self.get_condition_loop.exec_()

    def send_condition(self, screen_num, cond_name, cond_num, search):
        ret = self.kiwoom.dynamicCall(
            "SendCondition(QString, QString, int, int)", screen_num, cond_name, cond_num, search)
        if ret == 1:
            self.event_log.append("실시간 조건 종목 불러오기 성공")
            self.get_cond_item_loop = QEventLoop()
            self.get_cond_item_loop.exec_()
        else:
            self.event_log.append("실시간 조건 종목 불러오기 실패")

    def send_condition_stop(self, screen_num, cond_name, cond_num):
        self.kiwoom.dynamicCall(
            "SendConditionStop(Qstring, Qstring, int)", screen_num, cond_name, cond_num)

    # input tr value before comm with server
    def set_input_value(self, id, value):
        self.kiwoom.dynamicCall("SetInputValue(QString, QString", id, value)

    # get comm data
    def comm_rq_data(self, rqname, trcode, next, screen_no):
        self.kiwoom.dynamicCall(
            "CommRqData(QString, QString, int, QString)", rqname, trcode, next, screen_no)

        if trcode == "opt10031":
            self.tr_event_loop = QEventLoop()
            self.tr_event_loop.exec_()

    def send_order(self, rqname, screen_no, acc_no, order_type, code, quantity, price, hoga, order_no):
        order_type_lookup = {1: '신규매수', 2: '신규매도', 3: '매수취소', 4: '매도취소'}

        errcode = self.kiwoom.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                                          [rqname, screen_no, acc_no, order_type, code, quantity, price, hoga, order_no])
        current_time = QTime.currentTime()
        text_time = current_time.toString("hh:mm:ss")
        time_msg = "[" + text_time + "]"
        log = order_type_lookup[order_type] + " : " + \
            self.get_master_code_name(code) + ", " + \
            str(quantity) + "주"
        self.event_log.append(time_msg)
        self.event_log.append(log)
        return errcode

    def get_chejan_data(self, fid):
        ret = self.kiwoom.dynamicCall("GetChejanData(int)", fid)
        return ret

    def get_master_code_name(self, code):
        code_name = self.kiwoom.dynamicCall("GetMasterCodeName(Qstring)", code)
        return code_name


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main = autoBot()
    main.show()
    app.exec_()
