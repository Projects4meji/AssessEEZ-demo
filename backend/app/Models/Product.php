<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class Product extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'code',
        'name',
        'description',
        'category_id',
        'brand_id',
        'condition_id',
        'price',
        'created_at',
        'updated_at',
        'deleted_at',
        'delivery_fee',
        'delivery_fee_type_id',
        'status',
        'user_id'
    ];

    public function category()
    {
        return $this->hasOne(Category::class, 'id', 'category_id');
    }

    public function brand()
    {
        return $this->hasOne(Brand::class, 'id', 'brand_id');
    }

    public function condition()
    {
        return $this->hasOne(Condition::class, 'id', 'condition_id');
    }

    public function colors()
    {
        return $this->hasMany(ProductColor::class, 'product_id');
    }

    public function sizes()
    {
        return $this->hasMany(ProductSize::class, 'product_id');
    }

    public function deliveryFeeType()
    {
        return $this->hasOne(DeliveryFeeType::class, 'id', 'delivery_fee_type_id');
    }

    public function user()
    {
        return $this->hasOne(User::class, 'id', 'user_id');
    }
}
