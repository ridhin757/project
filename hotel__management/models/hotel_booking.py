from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError


class HotelBooking(models.Model):
    _name = "hotel.booking"
    _inherit = ['mail.thread']
    _order = "check_in desc"

    partner_id = fields.Many2one('res.partner', string='Guest')
    check_in = fields.Datetime(string='Check In', default=fields.Datetime.now())
    check_out = fields.Datetime(string='Check Out', default=fields.Datetime.now())
    bed_type = fields.Selection([('single', 'Single'), ('dormitory', 'Dormitory'),
                                 ('double', 'Double')], string='Bed')
    facility_ids = fields.Many2many('hotel.facility', string='Facility')
    room_id = fields.Many2one("hotel.room", string='Room')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('check_in', 'Check In'),
        ('paid', 'Paid'),
        ('check_out', 'Check Out'),
        ('cancel', 'Cancel')], readonly=True, default='draft', string='State')
    name = fields.Char(string="Sequence Number", readonly=True, required=True,
                       copy=False, default='NEW')
    expected_days = fields.Integer(string='Expected Days')
    expected_checkout = fields.Date(compute='_compute_expected_checkout',
                                    string='Expected Checkout')
    add_guests = fields.One2many('hotel.guests', 'booking_id')
    number_person = fields.Integer(string='Number of Persons')
    current_check_out = fields.Boolean(string='Current Checkout')
    nextday_check_out = fields.Boolean(string='Nextday Checkout')
    food_id = fields.One2many('hotel.food', 'booking_id', string="Payments")
    payment = fields.Integer(string='Total Amount', readonly="1")
    food = fields.Integer(string='Food', related='food_id.sub_total_price')

    def _compute_expected_checkout(self):
        for record in self:
            date = record.check_in + relativedelta(days=record.expected_days)
            record.expected_checkout = date

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('hotel.booking')
        result = super(HotelBooking, self).create(vals)
        return result

    def action_cancel(self):
        for record in self:
            record.state = "cancel"

    def action_check_in(self):
        for record in self:
            record.state = "check_in"
            if self.number_person == self.env['hotel.guests'].search_count([
                ('booking_id', '=', self.name)]):
                if self.number_person != self.env['ir.attachment'].search_count(
                        [('res_id', '=', self.id)]):
                    raise UserError("address proof is not matched")
            else:
                raise UserError("guest number is not matched")
            for rec in self.room_id:
                rec.write({'state': 'not_available'})
            if record.expected_checkout == fields.Date.today():
                record.current_check_out = True
            if record.expected_checkout == fields.Date.today() + relativedelta(days=1):
                record.nextday_check_out = True

        return {
            'type': 'ir.actions.act_window',
            'name': 'Booking Invoice',
            'view_mode': 'form',
            'res_model': 'hotel.booking.invoice',
            'context': {
                #'default_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_check_in': self.check_in,
                'default_check_out': self.check_out,
                'default_number_person': self.number_person,
                'default_bed_type': self.bed_type,
                'default_facility_ids': self.facility_ids.ids,
                'default_add_guests': self.add_guests.id,
                'default_room_id': self.room_id.id,
                #'default_food_id': self.food_id.id,


            }
        }


    def action_check_out(self):
        for record in self:
            record.state = "check_out"
            for rec in self.room_id:
                for x in self.facility_ids:
                    rec.write({'state': 'available'})
                    record.payment = record.expected_days * rec.rent + record.expected_days * x.rent




class HotelFoodOrder(models.Model):
    _name = 'hotel.booking.invoice'
    _description = 'hotel booking invoice'

    name = fields.Char(string="Sequence Number", readonly=True, required=True,
                       copy=False, default='NEW')
    partner_id = fields.Many2one('res.partner', string='Guest', readonly=True)
    check_in = fields.Datetime(string='Check In', default=fields.Datetime.now(), readonly=True)
    check_out = fields.Datetime(string='Check Out',
                                default=fields.Datetime.now(), readonly=True)
    bed_type = fields.Selection(
        [('single', 'Single'), ('dormitory', 'Dormitory'),
         ('double', 'Double')], string='Bed', readonly=True)
    facility_ids = fields.Many2many('hotel.facility', string='Facility', readonly=True)
    room_id = fields.Many2one("hotel.room", string='Room', readonly=True)
    add_guests = fields.One2many('hotel.guests', 'booking_id', readonly=True)
    number_person = fields.Integer(string='Number of Persons', readonly=True)
    food_id = fields.One2many('hotel.food', 'booking_id', string="Payments", readonly=True)
    booking_id = fields.Many2one('hotel.booking', readonly=True)
    #id = fields.Integer(string='Id', readonly=True)
    state = fields.Selection([('unpaid', 'Unpaid'), ('paid', 'Paid')], readonly=True, default='unpaid', string='State')

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('hotel.booking.invoice')
        result = super(HotelFoodOrder, self).create(vals)
        return result

    def action_payment(self):
        for rec in self:
            rec.state = "paid"
        pay = self.env['hotel.booking'].search([('state', '=', 'check_in')])
        for pay in pay:
            if pay.partner_id == self.partner_id:
                pay.state = 'paid'